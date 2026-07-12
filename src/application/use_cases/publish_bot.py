"""PublishBotUseCase — публикация бота (BR-001 + BR-006, анти-TOCTOU)."""

from __future__ import annotations

from application.errors import ApplicationError, BotNotFoundError, FlowNotFoundError
from application.ports.bot_platform import (
    BotPlatformPort,
    PlatformFactory,
    RegisterWebhookCommand,
)
from application.ports.bot_repository import BotRepository
from application.ports.flow_repository import FlowRepository
from application.ports.token_vault import TokenVaultPort
from domain.bot.entities import Bot


class PublishBotUseCase:
    """Переводит бота Draft/Paused -> Published.

    Порядок проверок:
    1. токен подтверждается платформой через ``BotPlatformPort.verify_token``;
    2. черновик валидируется против CapabilityMatrix платформы (BR-006);
    3. условие публикации проверяет домен — ``Bot.publish`` (BR-001);
    4. черновик замораживается с ``expected_row_version`` провалидированного
       снапшота — конкурентное автосохранение даёт ConcurrencyError, а не
       публикацию невалидной версии (анти-TOCTOU);
    5. повторная публикация неизменённого черновика идемпотентна (тот же
       content_hash -> та же версия), поэтому ретрай после сбоя закрепления
       версии за ботом безопасен и не плодит версий-сирот;
    6. при заданном ``webhook_url_template`` вебхук регистрируется у платформы
       автоматически (ADR-0014) — публикация «выгружает» бота без ручного
       setWebhook; сбой регистрации не откатывает публикацию, ретрай publish
       повторит её благодаря идемпотентности (п. 5).

    ``webhook_url_template`` — шаблон с плейсхолдерами ``{platform}`` и
    ``{bot_id}``; форму пути знает composition root (он же регистрирует роут),
    application только подставляет значения.

    :raises BotNotFoundError | FlowNotFoundError: агрегаты не найдены.
    :raises domain.errors.FlowValidationError: сценарий не проходит BR-006.
    :raises domain.errors.BotPublicationError: нарушено условие BR-001.
    :raises application.errors.ConcurrencyError: черновик изменён после валидации.
    :raises application.errors.ApplicationError: платформа недоступна или
        отклонила регистрацию вебхука (бот при этом уже опубликован).
    """

    def __init__(
        self,
        bots: BotRepository,
        flows: FlowRepository,
        token_vault: TokenVaultPort,
        platform_factory: PlatformFactory,
        *,
        webhook_url_template: str | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        self._bots = bots
        self._flows = flows
        self._token_vault = token_vault
        self._platform_factory = platform_factory
        self._webhook_url_template = webhook_url_template
        self._webhook_secret = webhook_secret

    async def execute(self, bot_id: str, *, actor_id: str | None = None) -> Bot:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        if bot.flow_id is None:
            raise FlowNotFoundError(f"Боту {bot_id!r} не назначен сценарий")
        draft = await self._flows.get_draft(bot.flow_id)
        if draft is None:
            raise FlowNotFoundError(f"Сценарий {bot.flow_id!r} не найден")

        platform = self._platform_factory.for_platform(bot.platform)
        secret = await self._token_vault.retrieve(bot.token.vault_ref)
        token_is_valid = await platform.verify_token(secret)

        draft.flow.validate_for_publication(platform.capabilities())  # BR-006
        bot.publish(flow=draft.flow, token_is_valid=token_is_valid)  # BR-001

        # ADR-0008: замораживается ровно провалидированный снапшот черновика.
        version = await self._flows.publish(
            bot.flow_id,
            expected_row_version=draft.row_version,
            bot_id=bot.id,
            actor_id=actor_id,
        )
        bot.pin_published_version(version.id)

        await self._bots.save(bot)
        await self._register_webhook(bot, platform, secret)
        return bot

    async def _register_webhook(self, bot: Bot, platform: BotPlatformPort, token: str) -> None:
        """Шаг 6: авто-регистрация вебхука (ADR-0014); без шаблона — ручной режим (dev)."""
        if self._webhook_url_template is None:
            return
        url = self._webhook_url_template.format(platform=bot.platform.value, bot_id=bot.id)
        try:
            await platform.register_webhook(
                RegisterWebhookCommand(bot_token=token, url=url, secret=self._webhook_secret)
            )
        except ApplicationError as exc:
            # Бот уже опубликован — не маскируем это под отказ публикации.
            raise ApplicationError(
                f"Бот {bot.id!r} опубликован, но вебхук не зарегистрирован: {exc}. "
                "Повторите публикацию — она идемпотентна и повторит регистрацию."
            ) from exc
