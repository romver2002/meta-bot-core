"""AuthenticateMiniAppUseCase — доверие пользователю mini app по init data (BR-007)."""

from __future__ import annotations

from application.errors import BotNotFoundError, MiniAppAuthError
from application.ports.bot_platform import MiniAppIdentity, PlatformFactory
from application.ports.bot_repository import BotRepository
from application.ports.token_vault import TokenVaultPort


class AuthenticateMiniAppUseCase:
    """Проверяет подпись init data токеном бота (из vault) и возвращает личность.

    Валидацию по правилам платформы делает адаптер за ``BotPlatformPort``
    (алгоритмы Telegram/MAX — specs/002-platform-deep-dive §3). Ядро init data
    не парсит и токен в сеть не отдаёт.

    :raises BotNotFoundError: бот не найден.
    :raises MiniAppAuthError: init data не прошла валидацию (BR-007).
    """

    def __init__(
        self,
        bots: BotRepository,
        token_vault: TokenVaultPort,
        platform_factory: PlatformFactory,
    ) -> None:
        self._bots = bots
        self._token_vault = token_vault
        self._platform_factory = platform_factory

    async def execute(self, bot_id: str, init_data: str) -> MiniAppIdentity:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        token = await self._token_vault.retrieve(bot.token.vault_ref)
        identity = self._platform_factory.for_platform(bot.platform).validate_init_data(token, init_data)
        if identity is None:
            raise MiniAppAuthError("Init data mini app не прошла валидацию (BR-007)")
        return identity
