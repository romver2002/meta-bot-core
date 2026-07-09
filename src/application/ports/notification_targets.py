"""Порты адресатов уведомлений: роль сценария -> external_chat_id (ADR-0010).

Flow ссылается только на символическую роль (`admin`, `developer`, ...);
`chat_id` — конфигурация конкретного бота (потенциальные ПДн), живёт за
портом и никогда не сериализуется в Flow-JSON.
"""

from __future__ import annotations

from typing import Protocol


class NotificationTargetResolverPort(Protocol):
    """Резолвит роль адресата в external_chat_id платформы (движок, блок notify)."""

    async def resolve(self, bot_id: str, role: str) -> str | None:
        """None — роль для бота не привязана; уведомление тихо пропускается.

        :raises ApplicationError: хранилище недоступно — best-effort-потребитель
            (блок notify) обязан пережить это, не роняя обработку update.
        """
        ...


class NotificationTargetWriterPort(Protocol):
    """Привязывает роль к chat_id (Admin API).

    :raises ApplicationError: хранилище недоступно для записи.
    """

    async def store(self, bot_id: str, role: str, chat_id: str) -> None: ...
