"""SubmitMiniAppResultUseCase (BR-007 -> Flow Engine) на фейках."""

import pytest

from application.errors import MiniAppAuthError
from application.ports.bot_platform import MiniAppIdentity
from application.use_cases.process_update import ProcessUpdateUseCase
from application.use_cases.submit_mini_app_result import SubmitMiniAppResultUseCase
from domain.bot.value_objects import BotStatus
from domain.flow.entities import Flow, Node, Trigger
from domain.flow.value_objects import NodeType, TriggerType
from domain.flow.version import FlowVersion, FlowVersionStatus
from tests.unit.application.fakes import (
    InMemoryBotRepository,
    InMemoryFlowRepository,
    InMemorySessionRepository,
    InMemoryTokenVault,
    StubHttpClient,
    StubNotificationTargets,
    StubPlatform,
    StubPlatformFactory,
    StubSecretResolver,
)
from tests.unit.factories import full_capabilities, make_bot

pytestmark = pytest.mark.unit


def _flow() -> Flow:
    return Flow(
        id="f",
        name="ma",
        nodes={"go": Node(id="go", type=NodeType.SEND_MESSAGE, params={"text": "Готово"})},
        triggers=(Trigger(id="t", type=TriggerType.MINI_APP_RESULT, target_node_id="go"),),
    )


async def _use_case(validator) -> tuple[SubmitMiniAppResultUseCase, StubPlatform]:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    sessions, vault = InMemorySessionRepository(), InMemoryTokenVault()
    platform = StubPlatform(full_capabilities(), init_data_validator=validator)
    factory = StubPlatformFactory(platform)

    bot = make_bot("bot-1", flow_id="f")
    bot.token = type(bot.token)(vault_ref=await vault.store("bot-1", "fake-token"))
    bot.status = BotStatus.PUBLISHED
    bot.published_flow_version_id = "v1"
    await bots.save(bot)
    flows.versions["v1"] = FlowVersion(
        id="v1", flow_id="f", status=FlowVersionStatus.PUBLISHED, flow=_flow(), version=1
    )
    process = ProcessUpdateUseCase(
        bots=bots,
        flows=flows,
        sessions=sessions,
        token_vault=vault,
        platform_factory=factory,
        http_client=StubHttpClient(),
        secrets=StubSecretResolver(),
        notifications=StubNotificationTargets(),
    )
    return SubmitMiniAppResultUseCase(
        bots=bots, token_vault=vault, platform_factory=factory, process_update=process
    ), platform


async def test_valid_result_fires_trigger_and_replies() -> None:
    use_case, platform = await _use_case(lambda _t, _d: MiniAppIdentity(external_user_id="9", params={}))
    await use_case.execute("bot-1", "signed-init-data", {"item": "Latte"})
    assert [c.text for c in platform.sent] == ["Готово"]


async def test_invalid_init_data_raises_and_engine_untouched() -> None:
    use_case, platform = await _use_case(lambda _t, _d: None)
    with pytest.raises(MiniAppAuthError, match="BR-007"):
        await use_case.execute("bot-1", "bad", {})
    assert platform.sent == []
