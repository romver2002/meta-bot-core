"""Flow Engine (ProcessUpdateUseCase): сценарные тесты на in-memory фейках."""

from __future__ import annotations

import pytest

from application.errors import FlowExecutionError
from application.use_cases.process_update import ProcessUpdateUseCase
from domain.bot.entities import MiniApp
from domain.bot.value_objects import BotStatus, Platform
from domain.events import IncomingEvent
from domain.flow.entities import Button, Flow, Node, Transition, Trigger
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType
from domain.flow.version import FlowVersion, FlowVersionStatus
from domain.session.entities import SessionStatus
from tests.unit.application.fakes import (
    InMemoryBotRepository,
    InMemoryFlowRepository,
    InMemorySessionRepository,
    InMemoryTokenVault,
    StubPlatform,
    StubPlatformFactory,
)
from tests.unit.factories import full_capabilities, make_bot

pytestmark = pytest.mark.unit

BOT_ID, USER, CHAT = "bot-1", "user-1", "chat-1"


def _flow() -> Flow:
    """/start -> приветствие -> вопрос имени; ответ -> условие -> vip/обычный финал.

    Плюс callback-меню: show_buttons с кнопкой next и текстовый триггер «меню».
    """
    nodes = {
        "greet": Node(id="greet", type=NodeType.SEND_MESSAGE, params={"text": "Привет, {name}!"}),
        "ask-name": Node(id="ask-name", type=NodeType.ASK, params={"prompt": "Как вас зовут?", "save_as": "name"}),
        "check": Node(id="check", type=NodeType.CONDITION, params={"expression": "name == 'Роман'"}),
        "vip": Node(id="vip", type=NodeType.SEND_MESSAGE, params={"text": "Добро пожаловать, {name}!"}),
        "plain": Node(id="plain", type=NodeType.SEND_MESSAGE, params={"text": "Рады видеть."}),
        "menu": Node(
            id="menu",
            type=NodeType.SHOW_BUTTONS,
            params={"text": "Куда дальше?"},
            buttons=(
                Button(label="Дальше", action=ButtonAction.NEXT, target="finish"),
                Button(label="Сайт", action=ButtonAction.URL, target="https://example.com"),
            ),
        ),
        "finish": Node(
            id="finish",
            type=NodeType.SAVE,
            params={"key": "finished", "value": "yes"},
        ),
        "bye": Node(id="bye", type=NodeType.SEND_MESSAGE, params={"text": "Готово, {name}."}),
    }
    return Flow(
        id="flow-1",
        name="Тестовый сценарий",
        nodes=nodes,
        triggers=(
            Trigger(id="t-start", type=TriggerType.START, target_node_id="greet"),
            Trigger(id="t-menu", type=TriggerType.TEXT, target_node_id="menu", config={"pattern": "меню"}),
        ),
        transitions=(
            Transition(source_node_id="greet", target_node_id="ask-name"),
            Transition(source_node_id="ask-name", target_node_id="check"),
            Transition(source_node_id="check", target_node_id="vip", on="true"),
            Transition(source_node_id="check", target_node_id="plain", on="false"),
            Transition(source_node_id="finish", target_node_id="bye"),
        ),
    )


def _event(event_type: TriggerType, *, text: str | None = None, payload: str | None = None) -> IncomingEvent:
    return IncomingEvent(
        platform=Platform.TELEGRAM,
        bot_id=BOT_ID,
        external_user_id=USER,
        external_chat_id=CHAT,
        event_type=event_type,
        text=text,
        payload=payload,
    )


async def _engine(flow: Flow, *, bot_status: BotStatus = BotStatus.PUBLISHED, mini_app_url: str | None = None):
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    sessions, vault = InMemorySessionRepository(), InMemoryTokenVault()
    platform_port = StubPlatform(full_capabilities())

    bot = make_bot(BOT_ID, flow_id=flow.id)
    bot.token = type(bot.token)(vault_ref=await vault.store(BOT_ID, "fake-token"))
    bot.status = bot_status
    bot.published_flow_version_id = "v1"
    if mini_app_url is not None:
        bot.mini_app = MiniApp(id="ma-1", bot_id=BOT_ID, url=mini_app_url)
    await bots.save(bot)
    flows.versions["v1"] = FlowVersion(
        id="v1", flow_id=flow.id, status=FlowVersionStatus.PUBLISHED, flow=flow, version=1
    )
    use_case = ProcessUpdateUseCase(
        bots=bots,
        flows=flows,
        sessions=sessions,
        token_vault=vault,
        platform_factory=StubPlatformFactory(platform_port),
    )
    return use_case, platform_port, sessions


async def test_start_runs_until_ask_and_waits() -> None:
    use_case, port, sessions = await _engine(_flow())

    await use_case.execute(_event(TriggerType.START))

    assert [c.text for c in port.sent] == ["Привет, !", "Как вас зовут?"]
    session = await sessions.get_active(BOT_ID, USER)
    assert session is not None
    assert session.awaiting_variable == "name"
    assert session.current_node_id == "ask-name"
    assert session.flow_version_id == "v1"


async def test_answer_flows_through_condition_true_branch() -> None:
    use_case, port, sessions = await _engine(_flow())
    await use_case.execute(_event(TriggerType.START))

    await use_case.execute(_event(TriggerType.TEXT, text="Роман"))

    assert port.sent[-1].text == "Добро пожаловать, Роман!"
    # Цепочка дошла до конца: сессия завершена, пара (Bot, user) свободна.
    assert await sessions.get_active(BOT_ID, USER) is None
    stored = sessions.storage[(BOT_ID, USER)]
    assert stored.status is SessionStatus.COMPLETED
    assert stored.variables == {"name": "Роман"}
    assert stored.awaiting_variable is None


async def test_answer_flows_through_condition_false_branch() -> None:
    use_case, port, _ = await _engine(_flow())
    await use_case.execute(_event(TriggerType.START))

    await use_case.execute(_event(TriggerType.TEXT, text="Иван"))

    assert port.sent[-1].text == "Рады видеть."


async def test_show_buttons_waits_then_next_button_continues() -> None:
    use_case, port, sessions = await _engine(_flow())

    await use_case.execute(_event(TriggerType.TEXT, text="меню"))
    assert port.sent[-1].text == "Куда дальше?"
    assert [b.label for b in port.sent[-1].buttons] == ["Дальше", "Сайт"]

    # Нажатие кнопки next: payload адаптера = id целевого узла.
    await use_case.execute(_event(TriggerType.CALLBACK, payload="finish"))

    stored = sessions.storage[(BOT_ID, USER)]
    assert stored.variables == {"finished": "yes"}  # save исполнился
    assert stored.status is SessionStatus.COMPLETED  # bye — конец цепочки
    assert port.sent[-1].text == "Готово, ."  # bye после save


async def test_paused_bot_ignores_events() -> None:
    use_case, port, sessions = await _engine(_flow(), bot_status=BotStatus.PAUSED)

    await use_case.execute(_event(TriggerType.START))

    assert port.sent == []
    assert await sessions.get_active(BOT_ID, USER) is None


async def test_unmatched_event_is_ignored() -> None:
    use_case, port, sessions = await _engine(_flow())

    await use_case.execute(_event(TriggerType.TEXT, text="что-то левое"))

    assert port.sent == []
    assert await sessions.get_active(BOT_ID, USER) is None


async def test_foreign_platform_event_is_ignored() -> None:
    use_case, port, _ = await _engine(_flow())
    event = IncomingEvent(
        platform=Platform.MAX,
        bot_id=BOT_ID,
        external_user_id=USER,
        external_chat_id=CHAT,
        event_type=TriggerType.START,
    )

    await use_case.execute(event)

    assert port.sent == []


async def test_completed_session_restarts_fresh() -> None:
    """После завершения сценария следующий /start начинает новую сессию."""
    use_case, port, sessions = await _engine(_flow())
    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_event(TriggerType.TEXT, text="Иван"))  # -> plain, конец
    first_id = sessions.storage[(BOT_ID, USER)].id

    await use_case.execute(_event(TriggerType.START))

    fresh = await sessions.get_active(BOT_ID, USER)
    assert fresh is not None
    assert fresh.id != first_id
    assert fresh.variables == {}  # чистое состояние, без старого name
    assert port.sent[-1].text == "Как вас зовут?"


def _mini_app_flow() -> Flow:
    """/start -> open_mini_app (ждём) -> подтверждение с результатом."""
    return Flow(
        id="flow-ma",
        name="Витрина",
        nodes={
            "open": Node(
                id="open",
                type=NodeType.OPEN_MINI_APP,
                params={"text": "Откройте витрину", "button_text": "Каталог", "save_as": "cart"},
            ),
            "confirm": Node(id="confirm", type=NodeType.SEND_MESSAGE, params={"text": "Ваш заказ: {cart}"}),
        },
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="open"),),
        transitions=(Transition(source_node_id="open", target_node_id="confirm"),),
    )


async def test_open_mini_app_sends_launch_button_and_waits() -> None:
    use_case, port, sessions = await _engine(_mini_app_flow(), mini_app_url="https://shop.example.com")

    await use_case.execute(_event(TriggerType.START))

    assert port.sent[-1].text == "Откройте витрину"
    button = port.sent[-1].buttons[0]
    assert button.action is ButtonAction.OPEN_MINI_APP
    assert button.target == "https://shop.example.com"
    session = await sessions.get_active(BOT_ID, USER)
    assert session is not None
    assert session.current_node_id == "open"  # ждём mini_app_result


async def test_mini_app_result_continues_scenario() -> None:
    use_case, port, sessions = await _engine(_mini_app_flow(), mini_app_url="https://shop.example.com")
    await use_case.execute(_event(TriggerType.START))

    await use_case.execute(_event(TriggerType.MINI_APP_RESULT, payload='{"item":"Latte"}'))

    assert port.sent[-1].text == 'Ваш заказ: {"item":"Latte"}'  # результат подставлен в {cart}
    assert sessions.storage[(BOT_ID, USER)].status is SessionStatus.COMPLETED


async def test_open_mini_app_without_attached_app_errors() -> None:
    use_case, _, _ = await _engine(_mini_app_flow(), mini_app_url=None)
    with pytest.raises(FlowExecutionError, match="mini app"):
        await use_case.execute(_event(TriggerType.START))


async def test_cyclic_flow_hits_step_limit() -> None:
    loop_flow = Flow(
        id="flow-loop",
        name="Цикл",
        nodes={
            "a": Node(id="a", type=NodeType.SAVE, params={"key": "x", "value": "1"}),
            "b": Node(id="b", type=NodeType.SAVE, params={"key": "y", "value": "2"}),
        },
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="a"),),
        transitions=(
            Transition(source_node_id="a", target_node_id="b"),
            Transition(source_node_id="b", target_node_id="a"),
        ),
    )
    use_case, _, _ = await _engine(loop_flow)

    with pytest.raises(FlowExecutionError, match="лимит"):
        await use_case.execute(_event(TriggerType.START))
