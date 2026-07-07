"""PublishBotUseCase — публикация бота (BR-001 + BR-006)."""

from __future__ import annotations

from application.errors import BotNotFoundError, FlowNotFoundError
from application.ports.bot_platform import PlatformFactory
from application.ports.bot_repository import BotRepository
from application.ports.flow_repository import FlowRepository
from application.ports.token_vault import TokenVaultPort
from domain.bot.entities import Bot


class PublishBotUseCase:
    """Переводит бота Draft/Paused -> Published.

    Порядок проверок:
    1. токен подтверждается платформой через ``BotPlatformPort.verify_token``
       (секрет достаётся из vault по ссылке и никуда не сохраняется);
    2. сценарий валидируется против ``CapabilityMatrix`` платформы —
       недоступные блоки отклоняются (BR-006, ``Flow.validate_for_publication``);
    3. само условие публикации проверяет домен — ``Bot.publish`` (BR-001).

    :raises BotNotFoundError: бот не найден.
    :raises FlowNotFoundError: сценарий не назначен или не найден.
    :raises domain.errors.FlowValidationError: сценарий не проходит BR-006.
    :raises domain.errors.BotPublicationError: нарушено условие BR-001.
    """

    def __init__(
        self,
        bots: BotRepository,
        flows: FlowRepository,
        token_vault: TokenVaultPort,
        platform_factory: PlatformFactory,
    ) -> None:
        self._bots = bots
        self._flows = flows
        self._token_vault = token_vault
        self._platform_factory = platform_factory

    async def execute(self, bot_id: str) -> Bot:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        if bot.flow_id is None:
            raise FlowNotFoundError(f"Боту {bot_id!r} не назначен сценарий")
        flow = await self._flows.get(bot.flow_id)
        if flow is None:
            raise FlowNotFoundError(f"Сценарий {bot.flow_id!r} не найден")

        platform = self._platform_factory.for_platform(bot.platform)
        secret = await self._token_vault.retrieve(bot.token.vault_ref)
        token_is_valid = await platform.verify_token(secret)

        flow.validate_for_publication(platform.capabilities())  # BR-006
        bot.publish(flow=flow, token_is_valid=token_is_valid)  # BR-001

        await self._bots.save(bot)
        return bot
