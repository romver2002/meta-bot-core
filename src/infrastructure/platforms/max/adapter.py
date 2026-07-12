"""MaxBotAdapter — реализация BotPlatformPort для MAX Bot API.

Greenfield сразу на ``platform-api2.max.ru``; токен — в заголовке
``Authorization`` (решение 2026-07-07, platform-reference.md). Токен не
логируется. SDK maxapi не используется — тонкий httpx-клиент (ADR-0009).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
from domain.capabilities import CapabilityMatrix
from domain.events import IncomingEvent
from domain.flow.entities import Button
from domain.flow.value_objects import ButtonAction
from infrastructure.platforms.capabilities_v1 import ENGINE_V1_CAPABILITIES
from infrastructure.platforms.max.mini_app_auth import validate_max_init_data
from infrastructure.platforms.max.webhook import parse_max_update
from infrastructure.platforms.mini_app_identity import identity_from_init_data


def _keyboard_attachment(buttons: tuple[Button, ...]) -> dict[str, Any] | None:
    """Доменные кнопки -> inline_keyboard-attachment MAX (по кнопке в строке)."""
    if not buttons:
        return None
    rows: list[list[dict[str, Any]]] = []
    for button in buttons:
        if button.action is ButtonAction.URL:
            rows.append([{"type": "link", "text": button.label, "url": button.target or ""}])
        elif button.action is ButtonAction.OPEN_MINI_APP:
            # open_app-кнопка MAX; точная схема поля URL — в списке «требует проверки»
            # (specs/002-platform-deep-dive §6) перед релизом MAX.
            rows.append([{"type": "open_app", "text": button.label, "web_app": {"url": button.target or ""}}])
        else:  # next и callback: payload = target (движок маршрутизирует)
            rows.append([{"type": "callback", "text": button.label, "payload": button.target or ""}])
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


class MaxBotAdapter:
    """Тонкий httpx-клиент MAX Bot API за BotPlatformPort."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://platform-api2.max.ru",
        init_data_max_age: int = 3600,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._init_data_max_age = init_data_max_age

    def capabilities(self) -> CapabilityMatrix:
        return ENGINE_V1_CAPABILITIES

    def parse_update(self, bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
        return parse_max_update(bot_id, payload)

    def validate_init_data(self, token: str, init_data: str) -> MiniAppIdentity | None:
        return identity_from_init_data(
            validate_max_init_data(token, init_data, max_age_seconds=self._init_data_max_age)
        )

    async def verify_token(self, token: str) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/me", headers={"Authorization": token})
        except httpx.HTTPError as exc:
            raise ApplicationError("MAX API недоступен для проверки токена") from exc
        return response.status_code == httpx.codes.OK

    async def register_webhook(self, command: RegisterWebhookCommand) -> None:
        """POST /subscriptions {url, secret}: ключ подписки — сам url, id платформа
        не отдаёт (specs/002, «Установка webhook» / «Ответ на подписку»); повторная
        подписка того же url идемпотентна. Только 443 и доверенный сертификат.
        """
        body: dict[str, Any] = {"url": command.url}
        if command.secret:
            body["secret"] = command.secret
        await self._simple_query(
            "POST",
            "/subscriptions",
            command.bot_token,
            params={},
            json_body=body,
            failure="MAX POST /subscriptions отклонён",
        )

    async def send_message(self, command: SendMessageCommand) -> None:
        body: dict[str, Any] = {"text": command.text}
        attachment = _keyboard_attachment(command.buttons)
        if attachment is not None:
            body["attachments"] = [attachment]
        try:
            response = await self._client.post(
                f"{self._base_url}/messages",
                params={"chat_id": command.external_chat_id},
                json=body,
                headers={"Authorization": command.bot_token},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # В тексте ошибки нет ни токена, ни содержимого сообщения.
            raise ApplicationError(f"MAX message не доставлен (chat={command.external_chat_id})") from exc

    async def edit_message(self, command: EditMessageCommand) -> None:
        """PUT /messages?message_id= — текст и клавиатура заменяются целиком.

        Семантика attachments у MAX: null «не менять», [] «удалить все»
        (specs/002, «Вложения при edit»). Пустые кнопки команды -> [] —
        протухшая клавиатура снимается, а не остаётся.
        """
        attachment = _keyboard_attachment(command.buttons)
        body: dict[str, Any] = {
            "text": command.text,
            "attachments": [attachment] if attachment is not None else [],
        }
        await self._simple_query(
            "PUT",
            "/messages",
            command.bot_token,
            params={"message_id": command.message_id},
            json_body=body,
            failure="MAX PUT /messages отклонён",
        )

    async def delete_message(self, command: DeleteMessageCommand) -> None:
        """DELETE /messages?message_id= (chat_id платформе не нужен)."""
        await self._simple_query(
            "DELETE",
            "/messages",
            command.bot_token,
            params={"message_id": command.message_id},
            json_body=None,
            failure="MAX DELETE /messages отклонён",
        )

    async def _simple_query(
        self,
        method: str,
        path: str,
        token: str,
        *,
        params: dict[str, str],
        json_body: dict[str, Any] | None,
        failure: str,
    ) -> None:
        """Вызов с ответом SimpleQueryResult: {success, message?}.

        В отличие от POST /messages, поле ``message`` здесь — СТРОКА ошибки,
        а не объект Message (specs/002, «Форма ответа») — парсим отдельно.
        """
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                json=json_body,
                headers={"Authorization": token},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ApplicationError(failure) from exc
        payload = self._payload_or_none(response)
        if isinstance(payload, dict) and payload.get("success") is False:
            raise ApplicationError(f"{failure}: {payload.get('message') or 'success=false'}")

    @staticmethod
    def _payload_or_none(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError:
            return None

    async def answer_callback(self, command: AnswerCallbackCommand) -> None:
        """POST /answers?callback_id= — defensive-политика «всегда отвечать» (specs/002)."""
        try:
            response = await self._client.post(
                f"{self._base_url}/answers",
                params={"callback_id": command.callback_id},
                json={},
                headers={"Authorization": command.bot_token},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ApplicationError("MAX /answers не принят") from exc
