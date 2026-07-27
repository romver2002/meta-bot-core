"""Триггер external_event в движке (ADR-0017): матчинг имени, payload → переменные."""

from __future__ import annotations

import dataclasses

import pytest

from application.use_cases.process_update import ProcessUpdateUseCase
from domain.bot.value_objects import BotStatus, Platform
from domain.events import IncomingEvent
from domain.flow.entities import Button, Flow, Node, Trigger
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType
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

BOT_ID, CHAT = "bot-1", "chat-owner"


def _flow(trigger_config: dict[str, str] | None) -> Flow:
    """external_event -> карточка с {подстановками} из payload события."""
    nodes = {
        "card": Node(
            id="card",
            type=NodeType.SEND_MESSAGE,
            params={"text": "{title} · {budget}"},
        ),
    }
    return Flow(
        id="flow-1",
        name="Внешнее событие",
        nodes=nodes,
        triggers=(
            Trigger(
                id="t-ext",
                type=TriggerType.EXTERNAL_EVENT,
                target_node_id="card",
                config=trigger_config or {},
            ),
        ),
        transitions=(),
    )


async def _engine(flow: Flow) -> tuple[ProcessUpdateUseCase, StubPlatform, InMemorySessionRepository]:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    sessions, vault = InMemorySessionRepository(), InMemoryTokenVault()
    platform_port = StubPlatform(full_capabilities())
    bot = make_bot(BOT_ID, flow_id=flow.id)
    bot.token = type(bot.token)(vault_ref=await vault.store(BOT_ID, "fake-token"))
    bot.status = BotStatus.PUBLISHED
    bot.published_flow_version_id = "v1"
    await bots.save(bot)
    flows.versions["v1"] = FlowVersion(id="v1", flow_id=flow.id, status=FlowVersionStatus.PUBLISHED, flow=flow, version=1)
    use_case = ProcessUpdateUseCase(
        bots=bots,
        flows=flows,
        sessions=sessions,
        token_vault=vault,
        platform_factory=StubPlatformFactory(platform_port),
        http_client=StubHttpClient(),
        secrets=StubSecretResolver(),
        notifications=StubNotificationTargets(),
    )
    return use_case, platform_port, sessions


def _event(name: str, variables: dict[str, str] | None = None) -> IncomingEvent:
    return IncomingEvent(
        platform=Platform.TELEGRAM,
        bot_id=BOT_ID,
        external_user_id=CHAT,
        external_chat_id=CHAT,
        event_type=TriggerType.EXTERNAL_EVENT,
        payload=name,
        variables=variables,
    )


async def test_named_trigger_renders_payload_variables() -> None:
    use_case, port, _ = await _engine(_flow({"event": "order_status_changed"}))

    await use_case.execute(_event("order_status_changed", {"title": "Бот с CRM", "budget": "50 000 ₽"}))

    assert [c.text for c in port.sent] == ["Бот с CRM · 50 000 ₽"]
    assert port.sent[0].external_chat_id == CHAT


async def test_mismatched_event_name_is_ignored_and_session_untouched() -> None:
    use_case, port, sessions = await _engine(_flow({"event": "order_status_changed"}))

    await use_case.execute(_event("other_event", {"title": "мимо"}))

    assert port.sent == []
    assert sessions.storage == {}  # несматченное событие не создаёт сессию и не пишет переменные


def _card_with_buttons_flow() -> Flow:
    """Карточка с кнопкой — как у внешнего потребителя («Подходит» / «Мимо»)."""
    return Flow(
        id="flow-1",
        name="Карточка события",
        nodes={
            "card": Node(
                id="card",
                type=NodeType.SHOW_BUTTONS,
                params={"text": "{title}"},
                buttons=(Button(label="Подходит", action=ButtonAction.NEXT, target="thanks"),),
            ),
            "thanks": Node(id="thanks", type=NodeType.SEND_MESSAGE, params={"text": "Принято"}),
        },
        triggers=(Trigger(id="t-ext", type=TriggerType.EXTERNAL_EVENT, target_node_id="card", config={}),),
        transitions=(),
    )


async def test_push_card_and_button_press_share_one_session() -> None:
    """Push-карточка и нажатие её кнопки — одна сессия.

    Событие адресуется по push-конвенции ``user:<id>`` (иначе боту MAX не
    написать первым), а последующий update от того же человека приходит с
    голым ``<id>`` — так его отдаёт вебхук. Сессия ведётся по идентичности,
    поэтому ключ обязан быть голым: положишь туда адрес как есть — нажатие
    не найдёт сессию и цепочка молча оборвётся.
    """
    use_case, port, _ = await _engine(_card_with_buttons_flow())
    push = dataclasses.replace(
        _event("order_status_changed", {"title": "Заказ"}),
        external_user_id="100000001",  # идентичность: адрес user:<id> без префикса
        external_chat_id="user:100000001",  # доставка: адрес по конвенции
    )

    await use_case.execute(push)
    await use_case.execute(
        IncomingEvent(
            platform=Platform.TELEGRAM,
            bot_id=BOT_ID,
            external_user_id="100000001",  # вебхук отдаёт голый id
            external_chat_id="100000001",
            event_type=TriggerType.CALLBACK,
            payload="thanks",
        )
    )

    assert port.sent[0].external_chat_id == "user:100000001"  # карточка ушла по конвенции
    assert [c.text for c in port.sent] == ["Заказ", "Принято"]  # цепочка продолжилась


async def test_trigger_without_event_config_catches_any_event() -> None:
    use_case, port, _ = await _engine(_flow(None))

    await use_case.execute(_event("whatever", {"title": "X", "budget": "Y"}))

    assert [c.text for c in port.sent] == ["X · Y"]
