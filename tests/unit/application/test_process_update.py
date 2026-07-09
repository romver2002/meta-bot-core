"""Flow Engine (ProcessUpdateUseCase): сценарные тесты на in-memory фейках."""

from __future__ import annotations

import itertools

import pytest

from application.errors import ApplicationError, FlowExecutionError
from application.ports.bot_platform import AnswerCallbackCommand, SendMessageCommand
from application.ports.http_client import HttpResponse
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
    StubHttpClient,
    StubNotificationTargets,
    StubPlatform,
    StubPlatformFactory,
    StubSecretResolver,
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


def _event(
    event_type: TriggerType,
    *,
    text: str | None = None,
    payload: str | None = None,
    callback_id: str | None = None,
) -> IncomingEvent:
    return IncomingEvent(
        platform=Platform.TELEGRAM,
        bot_id=BOT_ID,
        external_user_id=USER,
        external_chat_id=CHAT,
        event_type=event_type,
        text=text,
        payload=payload,
        callback_id=callback_id,
    )


async def _engine(
    flow: Flow,
    *,
    bot_status: BotStatus = BotStatus.PUBLISHED,
    mini_app_url: str | None = None,
    http_client: StubHttpClient | None = None,
    secrets: StubSecretResolver | None = None,
    notifications: StubNotificationTargets | None = None,
    platform_port: StubPlatform | None = None,
):
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    sessions, vault = InMemorySessionRepository(), InMemoryTokenVault()
    platform_port = platform_port or StubPlatform(full_capabilities())

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
        http_client=http_client or StubHttpClient(),
        secrets=secrets or StubSecretResolver(),
        notifications=notifications or StubNotificationTargets(),
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

    assert port.sent[-1].text == "Добро пожаловать, Роман!"  # переменная отработала в рендере
    # Цепочка дошла до конца: сессия завершена, пара (Bot, user) свободна.
    assert await sessions.get_active(BOT_ID, USER) is None
    stored = sessions.storage[(BOT_ID, USER)]
    assert stored.status is SessionStatus.COMPLETED
    assert stored.variables == {}  # BR-008: ПДн стёрты вместе с завершением сессии
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
    assert stored.status is SessionStatus.COMPLETED  # bye — конец цепочки
    assert stored.variables == {}  # BR-008: переменные не переживают завершение
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


def _http_flow() -> Flow:
    """/start -> http_request -> (next) ответ / (error) заглушка."""
    return Flow(
        id="f-http",
        name="http",
        nodes={
            "call": Node(
                id="call",
                type=NodeType.HTTP_REQUEST,
                params={
                    "method": "POST",
                    "url": "https://api.example.com/ask",
                    "headers": {"Authorization": "Bearer {{secret:api}}"},
                    "body": {"q": "hi"},
                    "response_map": {"answer": "choices.0.text"},
                },
            ),
            "reply": Node(id="reply", type=NodeType.SEND_MESSAGE, params={"text": "Ответ: {answer}"}),
            "oops": Node(id="oops", type=NodeType.SEND_MESSAGE, params={"text": "Сервис недоступен"}),
        },
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="call"),),
        transitions=(
            Transition(source_node_id="call", target_node_id="reply", on="next"),
            Transition(source_node_id="call", target_node_id="oops", on="error"),
        ),
    )


async def test_http_request_injects_secret_and_maps_response() -> None:
    http = StubHttpClient(HttpResponse(status_code=200, json={"choices": [{"text": "42"}]}, text=""))
    use_case, port, _ = await _engine(_http_flow(), http_client=http, secrets=StubSecretResolver({"api": "KEY-123"}))

    await use_case.execute(_event(TriggerType.START))

    # Секрет подставлен из хранилища, а НЕ хранится в определении Flow.
    assert http.calls[0]["headers"] == {"Authorization": "Bearer KEY-123"}
    assert http.calls[0]["json_body"] == {"q": "hi"}
    assert port.sent[-1].text == "Ответ: 42"  # поле ответа смаплено в {answer}


async def test_http_request_error_routes_to_error_branch() -> None:
    http = StubHttpClient(HttpResponse(status_code=503, json=None, text="down"))
    use_case, port, _ = await _engine(_http_flow(), http_client=http)

    await use_case.execute(_event(TriggerType.START))

    assert port.sent[-1].text == "Сервис недоступен"


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


async def test_save_values_map_sets_and_wipes_many_variables() -> None:
    """Save с values-маппингом (каталог блоков): несколько переменных одним узлом."""
    flow = Flow(
        id="flow-multisave",
        name="Мульти-save",
        nodes={
            "seed": Node(id="seed", type=NodeType.SAVE, params={"values": {"a": "1", "b": "2"}}),
            "wipe": Node(id="wipe", type=NodeType.SAVE, params={"values": {"a": "", "b": ""}}),
            "done": Node(id="done", type=NodeType.SEND_MESSAGE, params={"text": "a={a} b={b}"}),
        },
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="seed"),),
        transitions=(
            Transition(source_node_id="seed", target_node_id="wipe"),
            Transition(source_node_id="wipe", target_node_id="done"),
        ),
    )
    use_case, port, _ = await _engine(flow)

    await use_case.execute(_event(TriggerType.START))

    assert port.sent[-1].text == "a= b="  # обе переменные затёрты одним узлом


# ── подтверждение нажатия (answer_callback) ──────────────────────────────────


async def test_regular_click_is_acknowledged_once_and_scenario_runs() -> None:
    use_case, port, _ = await _engine(_flow())
    await use_case.execute(_event(TriggerType.TEXT, text="меню"))  # show_buttons ждёт нажатия

    await use_case.execute(_event(TriggerType.CALLBACK, payload="finish", callback_id="cbq-1"))

    assert [c.callback_id for c in port.answered] == ["cbq-1"]  # ровно один ack
    assert port.answered[0].bot_token == "fake-token"  # в команду ушёл секрет из vault, не vault_ref
    assert port.sent[-1].text == "Готово, ."  # ack и сценарий сосуществуют


async def test_callback_is_acknowledged_even_when_unrecognized() -> None:
    use_case, port, _ = await _engine(_flow())
    await use_case.execute(_event(TriggerType.START))
    sent_before = len(port.sent)

    # Протухшая кнопка: payload никуда не матчится, но спиннер обязан погаснуть.
    await use_case.execute(_event(TriggerType.CALLBACK, payload="ghost", callback_id="cbq-9"))

    assert [c.callback_id for c in port.answered] == ["cbq-9"]
    assert len(port.sent) == sent_before  # маршрутизация нажатие проигнорировала


async def test_callback_on_paused_bot_is_still_acknowledged() -> None:
    # Пауза — главный источник протухших кнопок: бот молчит, но спиннер гасим.
    use_case, port, _ = await _engine(_flow(), bot_status=BotStatus.DRAFT)

    await use_case.execute(_event(TriggerType.CALLBACK, payload="finish", callback_id="cbq-5"))

    assert [c.callback_id for c in port.answered] == ["cbq-5"]
    assert port.sent == []  # сценарий не исполняется


async def test_event_without_callback_id_is_not_acknowledged() -> None:
    use_case, port, _ = await _engine(_flow())

    await use_case.execute(_event(TriggerType.TEXT, text="меню"))  # текст — не нажатие

    assert port.answered == []


class _AckFailingPlatform(StubPlatform):
    """Подтверждение колбэка падает; доставка сообщений работает."""

    async def answer_callback(self, command: AnswerCallbackCommand) -> None:
        raise ApplicationError("ack не принят")


async def test_ack_failure_does_not_break_scenario() -> None:
    use_case, port, _ = await _engine(
        _flow(), platform_port=_AckFailingPlatform(full_capabilities())
    )
    await use_case.execute(_event(TriggerType.TEXT, text="меню"))  # show_buttons «Куда дальше?»

    await use_case.execute(_event(TriggerType.CALLBACK, payload="finish", callback_id="cbq-1"))

    assert port.sent[-1].text == "Готово, ."  # цепочка исполнилась несмотря на сбой ack


# ── блок notify (ADR-0010) ───────────────────────────────────────────────────


def _notify_flow() -> Flow:
    """/start -> save имени -> notify админу -> финал пользователю."""
    nodes = {
        "form": Node(id="form", type=NodeType.SAVE, params={"key": "name", "value": "Иван"}),
        "notify": Node(id="notify", type=NodeType.NOTIFY, params={"to": "admin", "text": "Заявка от {name}"}),
        "done": Node(id="done", type=NodeType.SEND_MESSAGE, params={"text": "Принято, {name}."}),
    }
    return Flow(
        id="flow-notify",
        name="Уведомление",
        nodes=nodes,
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="form"),),
        transitions=(
            Transition(source_node_id="form", target_node_id="notify"),
            Transition(source_node_id="notify", target_node_id="done"),
        ),
    )


class _FailingToChatPlatform(StubPlatform):
    """Доставка в заданный chat_id падает (получатель заблокировал бота)."""

    def __init__(self, failing_chat_id: str) -> None:
        super().__init__(full_capabilities())
        self._failing_chat_id = failing_chat_id

    async def send_message(self, command: SendMessageCommand) -> None:
        if command.external_chat_id == self._failing_chat_id:
            raise ApplicationError("получатель недоступен")
        await super().send_message(command)


async def test_notify_delivers_to_role_and_continues() -> None:
    use_case, port, _ = await _engine(
        _notify_flow(), notifications=StubNotificationTargets({"admin": "admin-chat"})
    )

    await use_case.execute(_event(TriggerType.START))

    admin_message, user_message = port.sent
    assert admin_message.external_chat_id == "admin-chat"
    assert admin_message.text == "Заявка от Иван"  # переменные сценария интерполированы
    assert user_message.external_chat_id == CHAT
    assert user_message.text == "Принято, Иван."


async def test_notify_unbound_role_is_skipped_and_chain_continues() -> None:
    use_case, port, _ = await _engine(_notify_flow(), notifications=StubNotificationTargets())

    await use_case.execute(_event(TriggerType.START))

    assert [c.external_chat_id for c in port.sent] == [CHAT]  # только финал пользователю
    assert port.sent[0].text == "Принято, Иван."


async def test_notify_delivery_failure_does_not_break_user_chain() -> None:
    use_case, port, _ = await _engine(
        _notify_flow(),
        notifications=StubNotificationTargets({"admin": "admin-chat"}),
        platform_port=_FailingToChatPlatform("admin-chat"),
    )

    await use_case.execute(_event(TriggerType.START))

    # Уведомление упало (best-effort), но пользователь получил свой ответ.
    assert [c.external_chat_id for c in port.sent] == [CHAT]
    assert port.sent[0].text == "Принято, Иван."


class _FailingResolver:
    """Хранилище адресатов недоступно (битый файл и т.п., контракт порта)."""

    async def resolve(self, bot_id: str, role: str) -> str | None:
        raise ApplicationError("хранилище повреждено")


async def test_notify_resolver_failure_does_not_break_user_chain() -> None:
    use_case, port, _ = await _engine(_notify_flow(), notifications=_FailingResolver())

    await use_case.execute(_event(TriggerType.START))

    # Сбой резолва роли — тоже best-effort: пользовательская цепочка дошла до конца.
    assert [c.external_chat_id for c in port.sent] == [CHAT]
    assert port.sent[0].text == "Принято, Иван."


async def test_notify_neutralizes_control_characters_in_variables() -> None:
    ask_flow = Flow(
        id="flow-spoof",
        name="Спуфинг",
        nodes={
            "ask": Node(id="ask", type=NodeType.ASK, params={"prompt": "Имя?", "save_as": "name"}),
            "notify": Node(id="notify", type=NodeType.NOTIFY, params={"to": "admin", "text": "Заявка от {name}"}),
            "done": Node(id="done", type=NodeType.SEND_MESSAGE, params={"text": "Принято."}),
        },
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="ask"),),
        transitions=(
            Transition(source_node_id="ask", target_node_id="notify"),
            Transition(source_node_id="notify", target_node_id="done"),
        ),
    )
    use_case, port, _ = await _engine(
        ask_flow, notifications=StubNotificationTargets({"admin": "admin-chat"})
    )
    await use_case.execute(_event(TriggerType.START))

    await use_case.execute(_event(TriggerType.TEXT, text="Иван\n📞 Контакт: fake\u202e"))

    admin_message = next(c for c in port.sent if c.external_chat_id == "admin-chat")
    assert "\n" not in admin_message.text  # перевод строки не дорисовал «поле» карточки
    assert "\u202e" not in admin_message.text  # bidi-переопределение удалено
    assert admin_message.text == "Заявка от Иван ⏎ 📞 Контакт: fake"


async def test_chain_of_exactly_max_steps_completes() -> None:
    from application.use_cases.process_update import MAX_STEPS

    node_ids = [f"n{i}" for i in range(MAX_STEPS)]
    linear_flow = Flow(
        id="flow-max",
        name="Ровно лимит",
        nodes={nid: Node(id=nid, type=NodeType.SAVE, params={"key": nid, "value": "x"}) for nid in node_ids},
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id=node_ids[0]),),
        transitions=tuple(
            Transition(source_node_id=a, target_node_id=b) for a, b in itertools.pairwise(node_ids)
        ),
    )
    use_case, _, sessions = await _engine(linear_flow)

    await use_case.execute(_event(TriggerType.START))  # не бросает «Превышен лимит»

    stored = sessions.storage[(BOT_ID, USER)]
    assert stored.status is SessionStatus.COMPLETED  # цепочка ровно в MAX_STEPS — не цикл
