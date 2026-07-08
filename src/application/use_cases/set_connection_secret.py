"""SetConnectionSecretUseCase — задать секрет подключения бота (ключ внешнего API)."""

from __future__ import annotations

from application.errors import BotNotFoundError
from application.ports.bot_repository import BotRepository
from application.ports.connection_secrets import ConnectionSecretWriterPort


class SetConnectionSecretUseCase:
    """Сохраняет секрет интеграции (ключ OpenRouter/CRM/…) по имени.

    Секрет — не bot-token: это ключ внешнего API, на который ссылается блок
    http_request как ``{{secret:имя}}``. В определение Flow значение не попадает.

    :raises BotNotFoundError: бот не найден.
    """

    def __init__(self, bots: BotRepository, secrets: ConnectionSecretWriterPort) -> None:
        self._bots = bots
        self._secrets = secrets

    async def execute(self, bot_id: str, name: str, value: str) -> None:
        if await self._bots.get(bot_id) is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        await self._secrets.store(bot_id, name, value)
