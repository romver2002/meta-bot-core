"""ListBotsUseCase — реестр ботов конструктора для Admin API («Мои боты»)."""

from __future__ import annotations

from application.ports.bot_repository import BotRepository
from domain.bot.entities import Bot


class ListBotsUseCase:
    """Возвращает всех ботов инсталляции, новые первыми.

    Admin API пока работает в доверенной среде без IAM (см. admin_routes.py);
    после появления владельцев список сузится до ботов текущего owner_id.
    """

    def __init__(self, bots: BotRepository) -> None:
        self._bots = bots

    async def execute(self) -> list[Bot]:
        return await self._bots.list_all()
