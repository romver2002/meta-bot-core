"""AttachMiniAppUseCase — привязка mini app к боту (BR-003)."""

from __future__ import annotations

import uuid

from application.errors import BotNotFoundError
from application.ports.bot_repository import BotRepository
from domain.bot.entities import Bot, MiniApp


class AttachMiniAppUseCase:
    """Создаёт/заменяет mini app бота. HTTPS-инвариант URL — в ``MiniApp`` (BR-003).

    :raises BotNotFoundError: бот не найден.
    :raises domain.errors.MiniAppInvariantError: URL не HTTPS.
    """

    def __init__(self, bots: BotRepository) -> None:
        self._bots = bots

    async def execute(self, bot_id: str, url: str, *, title: str = "") -> Bot:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        mini_app = MiniApp(id=uuid.uuid4().hex, bot_id=bot.id, url=url, title=title)
        bot.attach_mini_app(mini_app)
        await self._bots.save(bot)
        return bot
