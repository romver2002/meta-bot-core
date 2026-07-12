"""PublishBotUseCase: оркестрация BR-001 (токен+Flow), BR-006 (capabilities) и вебхука (ADR-0014)."""

import pytest

from application.errors import ApplicationError, BotNotFoundError, FlowNotFoundError
from application.use_cases.publish_bot import PublishBotUseCase
from domain.bot.value_objects import BotStatus
from domain.capabilities import CapabilityMatrix
from domain.errors import BotPublicationError, FlowValidationError
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType
from tests.unit.application.fakes import (
    InMemoryBotRepository,
    InMemoryFlowRepository,
    InMemoryTokenVault,
    StubPlatform,
    StubPlatformFactory,
)
from tests.unit.factories import full_capabilities, make_bot, make_flow

pytestmark = pytest.mark.unit

WEBHOOK_TEMPLATE = "https://bots.example/webhooks/{platform}/{bot_id}"


async def _prepared_use_case(
    platform_port: StubPlatform,
    *,
    webhook_url_template: str | None = None,
    webhook_secret: str | None = None,
) -> tuple[PublishBotUseCase, InMemoryBotRepository]:
    bots, flows, vault = InMemoryBotRepository(), InMemoryFlowRepository(), InMemoryTokenVault()
    bot = make_bot()
    bot.token = type(bot.token)(vault_ref=await vault.store(bot.id, "fake-token"))
    await bots.save(bot)
    await flows.save_draft(make_flow(), expected_row_version=None)
    factory = StubPlatformFactory(platform_port)
    return (
        PublishBotUseCase(
            bots=bots,
            flows=flows,
            token_vault=vault,
            platform_factory=factory,
            webhook_url_template=webhook_url_template,
            webhook_secret=webhook_secret,
        ),
        bots,
    )


async def test_publish_happy_path_br001_br006() -> None:
    platform_port = StubPlatform(full_capabilities(), token_is_valid=True)
    use_case, bots = await _prepared_use_case(platform_port)

    bot = await use_case.execute("bot-1")

    assert bot.status is BotStatus.PUBLISHED
    assert bots.storage["bot-1"].status is BotStatus.PUBLISHED
    # Токен проверялся у платформы значением из vault.
    assert platform_port.verified_tokens == ["fake-token"]
    # ADR-0008: за ботом закреплена замороженная версия сценария.
    assert bot.published_flow_version_id == "flow-1:v1"


async def test_publish_rejects_invalid_token_br001() -> None:
    platform_port = StubPlatform(full_capabilities(), token_is_valid=False)
    use_case, bots = await _prepared_use_case(platform_port)

    with pytest.raises(BotPublicationError, match="BR-001"):
        await use_case.execute("bot-1")
    assert bots.storage["bot-1"].status is BotStatus.DRAFT


async def test_publish_rejects_unsupported_block_br006() -> None:
    limited = CapabilityMatrix(
        node_types=frozenset(NodeType) - {NodeType.ASK},
        trigger_types=frozenset(TriggerType),
        button_actions=frozenset(ButtonAction),
    )
    use_case, bots = await _prepared_use_case(StubPlatform(limited, token_is_valid=True))

    with pytest.raises(FlowValidationError, match="BR-006"):
        await use_case.execute("bot-1")
    assert bots.storage["bot-1"].status is BotStatus.DRAFT


async def test_publish_registers_webhook_when_base_url_configured_adr0014() -> None:
    platform_port = StubPlatform(full_capabilities(), token_is_valid=True)
    use_case, _ = await _prepared_use_case(
        platform_port, webhook_url_template=WEBHOOK_TEMPLATE, webhook_secret="wh-s3cret"
    )

    bot = await use_case.execute("bot-1")

    assert bot.status is BotStatus.PUBLISHED
    (command,) = platform_port.registered
    # URL собран из шаблона composition root: платформа и bot_id подставлены.
    assert command.url == f"https://bots.example/webhooks/{bot.platform.value}/bot-1"
    assert command.bot_token == "fake-token"
    assert command.secret == "wh-s3cret"


async def test_publish_without_base_url_keeps_manual_webhook() -> None:
    platform_port = StubPlatform(full_capabilities(), token_is_valid=True)
    use_case, _ = await _prepared_use_case(platform_port)

    await use_case.execute("bot-1")

    assert platform_port.registered == []  # dev-режим: setWebhook остаётся ручным


async def test_publish_webhook_failure_reports_but_bot_stays_published() -> None:
    platform_port = StubPlatform(full_capabilities(), token_is_valid=True)
    platform_port.register_webhook_error = ApplicationError("платформа отклонила подписку")
    use_case, bots = await _prepared_use_case(platform_port, webhook_url_template=WEBHOOK_TEMPLATE)

    with pytest.raises(ApplicationError, match="опубликован, но вебхук не зарегистрирован"):
        await use_case.execute("bot-1")
    # Публикация состоялась ДО регистрации: ретрай publish идемпотентен
    # и повторит только регистрацию вебхука.
    assert bots.storage["bot-1"].status is BotStatus.PUBLISHED


async def test_publish_unknown_bot() -> None:
    use_case, _ = await _prepared_use_case(StubPlatform(full_capabilities()))
    with pytest.raises(BotNotFoundError):
        await use_case.execute("ghost")


async def test_publish_bot_without_flow() -> None:
    bots, flows, vault = InMemoryBotRepository(), InMemoryFlowRepository(), InMemoryTokenVault()
    bot = make_bot(flow_id=None)
    await bots.save(bot)
    use_case = PublishBotUseCase(
        bots=bots,
        flows=flows,
        token_vault=vault,
        platform_factory=StubPlatformFactory(StubPlatform(full_capabilities())),
    )
    with pytest.raises(FlowNotFoundError):
        await use_case.execute(bot.id)
