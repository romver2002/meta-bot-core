"""SubmitMiniAppResultUseCase — приём результата mini app (BR-007 + Flow Engine)."""

from __future__ import annotations

import json
from typing import Any

from application.errors import BotNotFoundError, MiniAppAuthError
from application.ports.bot_platform import PlatformFactory
from application.ports.bot_repository import BotRepository
from application.ports.token_vault import TokenVaultPort
from application.use_cases.process_update import ProcessUpdateUseCase, UpdateOutcome
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType


class SubmitMiniAppResultUseCase:
    """Валидирует init data (BR-007) и подаёт результат mini app в движок сценария.

    Результат становится событием ``mini_app_result``: если пользователь ждал
    его на блоке ``open_mini_app`` — сценарий продолжается, иначе срабатывает
    входной триггер ``mini_app_result`` (если он есть).

    :raises BotNotFoundError: бот не найден.
    :raises MiniAppAuthError: init data не прошла валидацию (BR-007).
    """

    def __init__(
        self,
        bots: BotRepository,
        token_vault: TokenVaultPort,
        platform_factory: PlatformFactory,
        process_update: ProcessUpdateUseCase,
    ) -> None:
        self._bots = bots
        self._token_vault = token_vault
        self._platform_factory = platform_factory
        self._process_update = process_update

    async def execute(self, bot_id: str, init_data: str, result: dict[str, Any]) -> UpdateOutcome:
        """Возвращает исход движка: «не исполнено» нельзя выдавать за «готово» (BR-012)."""
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        token = await self._token_vault.retrieve(bot.token.vault_ref)
        identity = self._platform_factory.for_platform(bot.platform).validate_init_data(token, init_data)
        if identity is None:
            raise MiniAppAuthError("Init data mini app не прошла валидацию (BR-007)")

        event = IncomingEvent(
            platform=bot.platform,
            bot_id=bot.id,
            external_user_id=identity.external_user_id,
            # Mini app открывается в личном чате с ботом → chat_id == user_id (v1);
            # уточнение chat из init data — в specs/002-platform-deep-dive.
            external_chat_id=identity.external_user_id,
            event_type=TriggerType.MINI_APP_RESULT,
            payload=json.dumps(result, ensure_ascii=False),
        )
        return await self._process_update.execute(event)
