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
from application.ports.bot_platform import AnswerCallbackCommand, MiniAppIdentity, SendMessageCommand
from domain.capabilities import CapabilityMatrix
from domain.events import IncomingEvent
from domain.flow.entities import Button
from domain.flow.value_objects import ButtonAction
from infrastructure.platforms.capabilities_v1 import ENGINE_V1_CAPABILITIES
from infrastructure.platforms.mini_app_identity import identity_from_init_data
from infrastructure.platforms.telegram.mini_app_auth import validate_telegram_init_data
from infrastructure.platforms.telegram.webhook import parse_telegram_update

_TOKEN_IN_PATH = re.compile(r"/bot[^/\s']+/")


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

    async def send_message(self, command: SendMessageCommand) -> None:
        body: dict[str, Any] = {"chat_id": command.external_chat_id, "text": command.text}
        keyboard = _keyboard(command.buttons)
        if keyboard is not None:
            body["reply_markup"] = keyboard
        try:
            response = await self._client.post(f"{self._base_url}/bot{command.bot_token}/sendMessage", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # В тексте ошибки нет ни токена, ни содержимого сообщения.
            _raise_scrubbed(f"Telegram sendMessage не доставлен (chat={command.external_chat_id})", exc)

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
