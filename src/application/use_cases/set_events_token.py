"""SetEventsTokenUseCase — задать events-токен бота (вход внешних событий, ADR-0017)."""

from __future__ import annotations

from application.errors import BotNotFoundError
from application.ports.bot_repository import BotRepository
from application.ports.events_token import EventsTokenWriterPort


class SetEventsTokenUseCase:
    """Сохраняет bot-scoped токен, которым внешние системы (CRM, агрегаторы,
    планировщики) аутентифицируют POST /bots/{id}/events. Хранилище отдельное от
    секретов подключений — в ``{{secret:*}}`` не резолвится (BR-010).

    :raises BotNotFoundError: бот не найден.
    """

    def __init__(self, bots: BotRepository, tokens: EventsTokenWriterPort) -> None:
        self._bots = bots
        self._tokens = tokens

    async def execute(self, bot_id: str, token: str) -> None:
        if await self._bots.get(bot_id) is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        await self._tokens.store(bot_id, token)
