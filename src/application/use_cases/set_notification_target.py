"""SetNotificationTargetUseCase — привязка роли уведомлений к chat_id (ADR-0010)."""

from __future__ import annotations

from application.errors import BotNotFoundError
from application.ports.bot_repository import BotRepository
from application.ports.notification_targets import NotificationTargetWriterPort


class SetNotificationTargetUseCase:
    """Задаёт адресата роли (`admin`, `developer`, ...) для блока notify.

    `chat_id` — конфигурация бота, не часть Flow: смена адресата не требует
    переопубликации сценария (BR-001 не затрагивается).

    :raises BotNotFoundError: бот не существует.
    """

    def __init__(self, bots: BotRepository, targets: NotificationTargetWriterPort) -> None:
        self._bots = bots
        self._targets = targets

    async def execute(self, bot_id: str, role: str, chat_id: str) -> None:
        if await self._bots.get(bot_id) is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        await self._targets.store(bot_id, role, chat_id)
