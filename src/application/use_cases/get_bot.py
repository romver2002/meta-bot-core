"""GetBotUseCase — чтение агрегата Bot для Admin API."""

from __future__ import annotations

from application.errors import BotNotFoundError
from application.ports.bot_repository import BotRepository
from domain.bot.entities import Bot


class GetBotUseCase:
    """Presentation не ходит в репозитории напрямую — только через use case."""

    def __init__(self, bots: BotRepository) -> None:
        self._bots = bots

    async def execute(self, bot_id: str) -> Bot:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        return bot
