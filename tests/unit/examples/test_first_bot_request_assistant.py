"""Пример «Умный помощник по заявкам» как ДАННЫЕ: валиден к публикации и
исполняется движком по всем ключевым путям на стабах (без реальных вызовов).

Регрессионно защищает поставляемый artefact examples/first-bot-request-assistant/
flow.definition.json: его контракт с движком (маршрутизация, секрет, интерполяция).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from application.ports.http_client import HttpClientPort, HttpResponse
from application.use_cases.process_update import ProcessUpdateUseCase
from domain.bot.value_objects import BotStatus, Platform
from domain.events import IncomingEvent
from domain.flow.codec import definition_to_flow
from domain.flow.entities import Flow
from domain.flow.value_objects import TriggerType
from domain.flow.version import FlowVersion, FlowVersionStatus
from infrastructure.platforms.capabilities_v1 import ENGINE_V1_CAPABILITIES
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

BOT_ID, USER, CHAT = "first-bot", "u1", "c1"
ADMIN_CHAT, DEV_CHAT = "admin-chat-1", "dev-chat-1"
API_KEY = "sk-test-KEY"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "examples" / "first-bot-request-assistant" / "flow.definition.json"


def _load_flow() -> Flow:
    definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    return definition_to_flow("first-bot-request-assistant", "Умный помощник по заявкам", definition)


def _openrouter_ok(content: str) -> StubHttpClient:
    return StubHttpClient(HttpResponse(status_code=200, json={"choices": [{"message": {"content": content}}]}, text=""))


class _SequenceHttp:
    """HttpClientPort, отдающий заданные ответы по порядку вызовов (для мультишага)."""

    def __init__(self, *responses: HttpResponse) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def request(
        self, *, method: str, url: str, headers: Mapping[str, str], json_body: object | None, timeout: float
    ) -> HttpResponse:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


async def _engine(*, http_client: HttpClientPort | None = None):
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    sessions, vault = InMemorySessionRepository(), InMemoryTokenVault()
    platform_port = StubPlatform(full_capabilities())

    flow = _load_flow()
    bot = make_bot(BOT_ID, flow_id=flow.id)
    bot.token = type(bot.token)(vault_ref=await vault.store(BOT_ID, "fake-token"))
    bot.status = BotStatus.PUBLISHED
    bot.published_flow_version_id = "v1"
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
        http_client=http_client or _openrouter_ok("ответ"),
        secrets=StubSecretResolver({"openrouter_api_key": API_KEY}),
        notifications=StubNotificationTargets({"admin": ADMIN_CHAT, "developer": DEV_CHAT}),
    )
    return use_case, platform_port


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


def _click(target_node_id: str) -> IncomingEvent:
    """Нажатие кнопки: адаптер шлёт callback c payload = id целевого узла."""
    return _event(TriggerType.CALLBACK, payload=target_node_id)


# ── публикуемость ────────────────────────────────────────────────────────────


def test_example_flow_valid_for_publication() -> None:
    flow = _load_flow()
    # Не бросает: блоки/триггеры/кнопки в матрице v1, достижимость и детерминизм — ок.
    flow.validate_for_publication(ENGINE_V1_CAPABILITIES)
    assert len(flow.nodes) == 28


# ── каркас ──────────────────────────────────────────────────────────────────


async def test_start_shows_greeting_then_menu() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))

    assert len(port.sent) == 2
    assert "помощник" in port.sent[0].text
    assert port.sent[1].text == "Главное меню — чем помочь?"
    assert len(port.sent[1].buttons) == 6


# ── AI-ответ (живой вызов OpenRouter, здесь на стабе) ────────────────────────


async def test_ai_answer_injects_secret_and_interpolates_question() -> None:
    http = _openrouter_ok("Работаем на Telegram и MAX.")
    use_case, port = await _engine(http_client=http)

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("n_ask_prompt"))
    await use_case.execute(_event(TriggerType.TEXT, text="На каких платформах работаете?"))

    call = http.calls[0]
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == f"Bearer {API_KEY}"  # секрет подставлен за портом
    body = call["json_body"]
    assert body["messages"][1]["content"] == "На каких платформах работаете?"  # вопрос интерполирован
    assert "{{secret" not in json.dumps(body)  # секрет НЕ утёк в тело
    # Ответ показан пользователю с кнопками эскалации.
    assert port.sent[-1].text == "Работаем на Telegram и MAX."
    assert len(port.sent[-1].buttons) == 4


async def test_ai_empty_answer_routes_to_specialist() -> None:
    use_case, port = await _engine(http_client=_openrouter_ok(""))

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("n_ask_prompt"))
    await use_case.execute(_event(TriggerType.TEXT, text="вопрос вне базы"))

    assert "передать" in port.sent[-1].text.lower()  # экран честного хэндоффа


async def test_ai_http_error_routes_to_specialist() -> None:
    failing = StubHttpClient(HttpResponse(status_code=500, json={}, text=""))
    use_case, port = await _engine(http_client=failing)

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("n_ask_prompt"))
    await use_case.execute(_event(TriggerType.TEXT, text="любой вопрос"))

    assert "не получилось" in port.sent[-1].text.lower()


async def test_null_answer_after_previous_does_not_leak() -> None:
    # Регресс: второй вопрос в ТОЙ ЖЕ сессии, модель вернула content=null.
    # Остаточный ai_answer прошлого шага НЕ должен подмениться ответом (иначе
    # пользователь видит ответ на прошлый вопрос). Ждём честный хэндофф.
    http = _SequenceHttp(
        HttpResponse(status_code=200, json={"choices": [{"message": {"content": "Цена — 100."}}]}, text=""),
        HttpResponse(status_code=200, json={"choices": [{"message": {"content": None}}]}, text=""),
    )
    use_case, port = await _engine(http_client=http)

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("n_ask_prompt"))
    await use_case.execute(_event(TriggerType.TEXT, text="сколько стоит?"))
    assert port.sent[-1].text == "Цена — 100."

    await use_case.execute(_click("n_ask_prompt"))  # «Ещё вопрос»
    await use_case.execute(_event(TriggerType.TEXT, text="а скидки на опт бывают?"))

    assert "не получилось" in port.sent[-1].text.lower()  # хэндофф, не прошлый ответ
    assert "Цена — 100." not in port.sent[-1].text


# ── форма заявки ─────────────────────────────────────────────────────────────


async def test_request_form_collects_and_confirms() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))
    for answer in ("Иван", "+70000000000", "Нужен бот-помощник", "2 недели", "не определён"):
        await use_case.execute(_event(TriggerType.TEXT, text=answer))

    summary = port.sent[-1].text
    assert "Иван" in summary
    assert "+70000000000" in summary
    assert "Нужен бот-помощник" in summary

    await use_case.execute(_click("req_notify"))  # «✅ Подтвердить» -> notify -> финал

    admin_messages = [c for c in port.sent if c.external_chat_id == ADMIN_CHAT]
    assert len(admin_messages) == 1  # заявка реально доставлена админу (ADR-0010)
    assert "Иван" in admin_messages[0].text
    assert "+70000000000" in admin_messages[0].text

    done = port.sent[-1]
    assert done.external_chat_id == CHAT  # финал — пользователю
    assert "Иван" in done.text  # {req_name} интерполировано в подтверждение
    assert "+70000000000" in done.text  # {req_contact} интерполировано


async def test_developer_contact_delivers_message() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("dev_start"))
    await use_case.execute(_event(TriggerType.TEXT, text="Нужна интеграция с CRM"))
    await use_case.execute(_event(TriggerType.TEXT, text="@roman"))
    await use_case.execute(_click("dev_notify"))  # «📨 Отправить»

    dev_messages = [c for c in port.sent if c.external_chat_id == DEV_CHAT]
    assert len(dev_messages) == 1
    assert "Нужна интеграция с CRM" in dev_messages[0].text
    assert "@roman" in dev_messages[0].text
    assert port.sent[-1].external_chat_id == CHAT  # пользователь видит «Передал!»


async def test_free_text_at_menu_gets_hint_not_silence() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_event(TriggerType.TEXT, text="сколько стоит бот?"))  # без кнопки

    assert "Задать вопрос" in port.sent[-1].text  # подсказка вместо молчания
    assert len(port.sent[-1].buttons) == 2


async def test_confirm_survives_free_text_detour() -> None:
    # Регресс (must-fix роя): «да» на экране подтверждения уводит сессию на
    # подсказку (catch-all t_text); «✅ Подтвердить» обязана всё равно доставить.
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))
    for answer in ("Иван", "+70000000000", "Нужен бот", "2 недели", "не определён"):
        await use_case.execute(_event(TriggerType.TEXT, text=answer))
    await use_case.execute(_event(TriggerType.TEXT, text="да"))  # детур на подсказку

    await use_case.execute(_click("req_notify"))  # тап по «✅ Подтвердить» со старой карточки

    admin_messages = [c for c in port.sent if c.external_chat_id == ADMIN_CHAT]
    assert len(admin_messages) == 1  # заявка доставлена, не потеряна молча
    assert "Иван" in admin_messages[0].text
    assert port.sent[-1].external_chat_id == CHAT  # пользователь увидел «Готово»


async def test_stale_confirm_without_data_restarts_form_not_empty_card() -> None:
    # Протухшая кнопка «✅ Подтвердить» в свежей сессии (переменных нет):
    # guard-условие уводит на перезапуск формы, пустая карточка админу не уходит.
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_notify"))  # без заполнения формы

    assert [c for c in port.sent if c.external_chat_id == ADMIN_CHAT] == []
    # Guard увёл на перезапуск формы: интро req_start и первый вопрос анкеты.
    assert any("Оформим заявку" in c.text for c in port.sent)
    assert "Как к вам обращаться?" in port.sent[-1].text


async def test_menu_screen_button_survives_detour() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_event(TriggerType.TEXT, text="привет"))  # детур на подсказку

    await use_case.execute(_click("n_services"))  # старая кнопка меню

    assert "Коротко об услугах" in port.sent[-1].text  # фолбэк-триггер сработал


# ── устойчивость к «старым» клавиатурам: глобальный возврат в меню ───────────


async def test_menu_button_interrupts_form_midway() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))  # начали форму, ждём имя
    await use_case.execute(_click("n_menu"))  # нажали «В меню» со старого сообщения

    assert port.sent[-1].text == "Главное меню — чем помочь?"  # глобальный callback-триггер сработал
