"""CreateBotUseCase — создание бота по уже выданному платформой токену."""

from __future__ import annotations

import uuid

from application.errors import BotCreationError
from application.ports.bot_repository import BotRepository
from application.ports.token_vault import TokenVaultPort
from domain.bot.entities import Bot
from domain.bot.value_objects import Platform, Token


class CreateBotUseCase:
    """Заводит Bot в статусе Draft.

    BR-002: конструктор не создаёт платформенный аккаунт бота и не обходит
    модерацию/лимиты платформы — Bot создаётся только по уже выданному
    токену. Секрет сразу уходит в token vault; на агрегате остаётся лишь
    ссылка (``Token.vault_ref``).

    :raises BotCreationError: токен не передан (BR-002), некорректный формат
        bot_id или бот с таким id уже существует (create — не перезапись).
    """

    def __init__(self, bots: BotRepository, token_vault: TokenVaultPort) -> None:
        self._bots = bots
        self._token_vault = token_vault

    async def execute(
        self,
        *,
        name: str,
        platform: Platform,
        token_secret: str,
        bot_id: str | None = None,
    ) -> Bot:
        if not token_secret.strip():
            raise BotCreationError("BR-002: Bot заводится только по уже выданному платформой токену")
        new_id = self._validated_id(bot_id)
        if await self._bots.get(new_id) is not None:
            raise BotCreationError(f"Бот {new_id!r} уже существует — создание не перезаписывает")
        vault_ref = await self._token_vault.store(new_id, token_secret)
        bot = Bot(id=new_id, name=name, platform=platform, token=Token(vault_ref=vault_ref))
        await self._bots.save(bot)
        return bot

    @staticmethod
    def _validated_id(bot_id: str | None) -> str:
        if bot_id is None:
            return uuid.uuid4().hex
        try:
            return uuid.UUID(bot_id).hex
        except ValueError as exc:
            raise BotCreationError(f"bot_id должен быть UUID, получено: {bot_id!r}") from exc
