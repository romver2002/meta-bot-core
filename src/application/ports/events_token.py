"""Порты events-токена — аутентификация входа внешних событий (ADR-0017).

ВАЖНО: это ОТДЕЛЬНОЕ хранилище, не секреты подключений. Секреты подключений
резолвятся движком в ``{{secret:*}}`` блока http_request — положить туда
входной токен значит отдать его автору сценария исходящим запросом.
Events-токен интерполяции недоступен по построению (BR-010).
"""

from __future__ import annotations

from typing import Protocol


class EventsTokenResolverPort(Protocol):
    """Чтение ожидаемого токена (для проверки входящего X-Events-Token)."""

    async def resolve(self, bot_id: str) -> str | None: ...


class EventsTokenWriterPort(Protocol):
    """Запись токена (Admin API, PUT /bots/{id}/events-token)."""

    async def store(self, bot_id: str, token: str) -> None: ...
