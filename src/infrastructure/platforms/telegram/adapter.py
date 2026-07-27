"""TelegramBotAdapter — реализация BotPlatformPort для Telegram Bot API.

Особенность платформы: токен передаётся в пути URL
(``/bot{token}/method``, platform-reference.md). Токен не логируется.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, NoReturn

import httpx

from application.errors import ApplicationError
from application.ports.bot_platform import (
    AnswerCallbackCommand,
    DeleteMessageCommand,
    EditMessageCommand,
    MiniAppIdentity,
    RegisterWebhookCommand,
    SendMessageCommand,
)
from domain.addressing import address_identity
from domain.capabilities import CapabilityMatrix
from domain.events import IncomingEvent
from domain.flow.entities import Button
from domain.flow.value_objects import ButtonAction
from infrastructure.platforms.capabilities_v1 import ENGINE_V1_CAPABILITIES
from infrastructure.platforms.mini_app_identity import identity_from_init_data
from infrastructure.platforms.telegram.mini_app_auth import validate_telegram_init_data
from infrastructure.platforms.telegram.webhook import parse_telegram_update

_TOKEN_IN_PATH = re.compile(r"/bot[^/\s']+/")


def _message_id_as_int(message_id: str) -> int:
    """Нейтральный str-идентификатор -> Integer Telegram (specs/002, «Тип message_id»)."""
    try:
        return int(message_id)
    except ValueError as exc:
        raise ApplicationError(f"Telegram message_id не числовой: {message_id!r}") from exc


def _is_not_modified(response: httpx.Response | None) -> bool:
    """400 «message is not modified» — правка в идентичное содержимое, не сбой."""
    if response is None:
        return False
    try:
        description = response.json().get("description", "")
    except ValueError:
        return False
    return "message is not modified" in str(description)


def _raise_scrubbed(message: str, exc: httpx.HTTPError) -> NoReturn:
    """Оборачивает httpx-ошибку БЕЗ утечки токена.

    Текст httpx-исключений содержит URL с ``/bot<token>/`` — токен вычищается.
    Исходное исключение не чейнится, а ``__context__`` зануляется явно:
    ``from None`` лишь прячет контекст при печати, объект с токеном остался бы
    доступен интроспекции цепочки (architecture/security.md).
    """
    detail = _TOKEN_IN_PATH.sub("/bot***/", str(exc))
    error = ApplicationError(f"{message}: {detail}")
    try:
        raise error from None
    finally:
        error.__context__ = None


def _keyboard(buttons: tuple[Button, ...]) -> dict[str, Any] | None:
    """Доменные кнопки -> inline-клавиатура Telegram (по кнопке в строке)."""
    if not buttons:
        return None
    rows: list[list[dict[str, Any]]] = []
    for button in buttons:
        if button.action is ButtonAction.URL:
            rows.append([{"text": button.label, "url": button.target or ""}])
        elif button.action is ButtonAction.OPEN_MINI_APP:
            rows.append([{"text": button.label, "web_app": {"url": button.target or ""}}])
        else:  # next и callback: payload = target (движок маршрутизирует)
            rows.append([{"text": button.label, "callback_data": button.target or ""}])
    return {"inline_keyboard": rows}


class TelegramBotAdapter:
    """Тонкий httpx-клиент Telegram Bot API за BotPlatformPort."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://api.telegram.org",
        init_data_max_age: int = 3600,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._init_data_max_age = init_data_max_age

    def capabilities(self) -> CapabilityMatrix:
        return ENGINE_V1_CAPABILITIES

    def parse_update(self, bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
        return parse_telegram_update(bot_id, payload)

    def validate_init_data(self, token: str, init_data: str) -> MiniAppIdentity | None:
        return identity_from_init_data(
            validate_telegram_init_data(token, init_data, max_age_seconds=self._init_data_max_age)
        )

    async def verify_token(self, token: str) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/bot{token}/getMe")
        except httpx.HTTPError as exc:
            _raise_scrubbed("Telegram API недоступен для проверки токена", exc)
        return response.status_code == httpx.codes.OK and bool(response.json().get("ok"))

    async def register_webhook(self, command: RegisterWebhookCommand) -> None:
        """setWebhook: перезаписывает подписку идемпотентно (specs/002, «Установка webhook»).

        ``allowed_updates`` не сужаем: неподдерживаемые типы parse_update
        игнорирует, а сужение пришлось бы синхронизировать с движком (ADR-0014).
        """
        body: dict[str, Any] = {"url": command.url}
        if command.secret:
            body["secret_token"] = command.secret
        try:
            response = await self._client.post(f"{self._base_url}/bot{command.bot_token}/setWebhook", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            _raise_scrubbed("Telegram setWebhook не принят", exc)
        try:
            payload = response.json()
        except ValueError:
            # 2xx с не-JSON телом (страница туннеля/прокси): контракт порта —
            # только ApplicationError, сырой JSONDecodeError наружу не выпускаем.
            raise ApplicationError("Telegram setWebhook вернул не-JSON ответ") from None
        if not isinstance(payload, dict) or not bool(payload.get("ok")):
            # description платформы не содержит токена; url — не секрет.
            description = payload.get("description") if isinstance(payload, dict) else None
            raise ApplicationError(f"Telegram setWebhook отклонён: {description or 'ok=false'}")

    async def send_message(self, command: SendMessageCommand) -> None:
        # Конвенция адреса «user:<id>» (domain/addressing.py, ADR-0017): в личке
        # Telegram chat_id совпадает с user_id — префикс просто снимается
        # (симметрия с MAX, где он превращается в параметр user_id).
        chat_id = address_identity(command.external_chat_id)
        body: dict[str, Any] = {"chat_id": chat_id, "text": command.text}
        keyboard = _keyboard(command.buttons)
        if keyboard is not None:
            body["reply_markup"] = keyboard
        try:
            response = await self._client.post(f"{self._base_url}/bot{command.bot_token}/sendMessage", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # В тексте ошибки нет ни токена, ни содержимого сообщения.
            _raise_scrubbed(f"Telegram sendMessage не доставлен (chat={command.external_chat_id})", exc)

    async def edit_message(self, command: EditMessageCommand) -> None:
        """editMessageText: текст и inline-клавиатура заменяются целиком.

        reply_markup без кнопок не передаётся — Telegram при этом УБИРАЕТ
        клавиатуру (семантика EditMessageCommand: пусто = снять меню).
        Правка в идентичное содержимое («message is not modified») — успех.
        """
        body: dict[str, Any] = {
            "chat_id": address_identity(command.external_chat_id),
            "message_id": _message_id_as_int(command.message_id),
            "text": command.text,
        }
        keyboard = _keyboard(command.buttons)
        if keyboard is not None:
            body["reply_markup"] = keyboard
        try:
            response = await self._client.post(f"{self._base_url}/bot{command.bot_token}/editMessageText", json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if _is_not_modified(exc.response):
                return
            _raise_scrubbed(f"Telegram editMessageText отклонён (chat={command.external_chat_id})", exc)
        except httpx.HTTPError as exc:
            _raise_scrubbed(f"Telegram editMessageText не доставлен (chat={command.external_chat_id})", exc)

    async def delete_message(self, command: DeleteMessageCommand) -> None:
        """deleteMessage: у Telegram лимит давности 48 часов (platform-reference)."""
        body = {
            "chat_id": address_identity(command.external_chat_id),
            "message_id": _message_id_as_int(command.message_id),
        }
        try:
            response = await self._client.post(f"{self._base_url}/bot{command.bot_token}/deleteMessage", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            _raise_scrubbed(f"Telegram deleteMessage отклонён (chat={command.external_chat_id})", exc)

    async def answer_callback(self, command: AnswerCallbackCommand) -> None:
        """Зовёт answerCallbackQuery — без него у пользователя вечный спиннер."""
        try:
            response = await self._client.post(
                f"{self._base_url}/bot{command.bot_token}/answerCallbackQuery",
                json={"callback_query_id": command.callback_id},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            _raise_scrubbed("Telegram answerCallbackQuery не принят", exc)
