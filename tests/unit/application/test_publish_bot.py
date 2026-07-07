"""PublishBotUseCase: оркестрация BR-001 (токен+Flow) и BR-006 (capabilities)."""

import pytest

from application.errors import BotNotFoundError, FlowNotFoundError
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


async def _prepared_use_case(
    platform_port: StubPlatform,
) -> tuple[PublishBotUseCase, InMemoryBotRepository]:
    bots, flows, vault = InMemoryBotRepository(), InMemoryFlowRepository(), InMemoryTokenVault()
    bot = make_bot()
    bot.token = type(bot.token)(vault_ref=await vault.store(bot.id, "fake-token"))
    await bots.save(bot)
    await flows.save(make_flow())
    factory = StubPlatformFactory(platform_port)
    return (
        PublishBotUseCase(bots=bots, flows=flows, token_vault=vault, platform_factory=factory),
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
