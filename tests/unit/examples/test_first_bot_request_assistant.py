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
CRM_KEY = "crm-test-KEY"
DEFINITION_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "first-bot-request-assistant" / "flow.definition.json"
)


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
        secrets=StubSecretResolver({"openrouter_api_key": API_KEY, "crm_api_key": CRM_KEY}),
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
    assert len(flow.nodes) == 44


def test_no_pii_collection_path_bypasses_consent() -> None:
    # Структурный инвариант BR-008: в узлы сбора ПДн нельзя попасть мимо согласия.
    flow = _load_flow()
    pii_entry_nodes = {"req_ask_name", "dev_ask_message"}
    trigger_targets = {t.target_node_id for t in flow.triggers}
    assert trigger_targets & pii_entry_nodes == set()  # ни один триггер не ведёт в сбор ПДн
    consent_holders = {node.id for node in flow.nodes.values() for b in node.buttons if b.target in pii_entry_nodes}
    # Кнопки в сбор ПДн — только с экранов согласия и пост-согласийных экранов правки.
    assert consent_holders <= {"req_start", "req_summary", "dev_start", "dev_confirm"}
    transition_sources = {t.source_node_id for t in flow.transitions if t.target_node_id in pii_entry_nodes}
    assert transition_sources == set()  # и безусловных переходов в сбор ПДн нет


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
    assert "разрешаете" in port.sent[-1].text  # экран согласия на обработку ПДн (BR-008)
    await use_case.execute(_click("req_ask_name"))  # «✅ Согласен — продолжить»
    for answer in ("Иван", "+70000000000", "Нужен бот-помощник", "2 недели", "не определён"):
        await use_case.execute(_event(TriggerType.TEXT, text=answer))

    summary = port.sent[-1].text
    assert "Иван" in summary
    assert "+70000000000" in summary
    assert "Нужен бот-помощник" in summary

    await use_case.execute(_click("req_notify"))  # «✅ Подтвердить» -> notify -> wipe -> финал

    admin_messages = [c for c in port.sent if c.external_chat_id == ADMIN_CHAT]
    assert len(admin_messages) == 1  # заявка реально доставлена админу (ADR-0010)
    assert "Иван" in admin_messages[0].text
    assert "+70000000000" in admin_messages[0].text

    done = port.sent[-1]
    assert done.external_chat_id == CHAT  # финал — пользователю
    assert "Готово" in done.text  # без ПДн: переменные стёрты сразу после доставки (BR-008)

    # Повторный тап по протухшей «✅ Подтвердить»: данные стёрты -> guard не пускает,
    # дубль заявки админу не уходит.
    await use_case.execute(_click("req_notify"))
    assert len([c for c in port.sent if c.external_chat_id == ADMIN_CHAT]) == 1


async def _fill_request_form(use_case: ProcessUpdateUseCase) -> None:
    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))
    await use_case.execute(_click("req_ask_name"))  # «✅ Согласен — продолжить»
    for answer in ("Иван", "+70000000000", "Нужен бот-помощник", "2 недели", "не определён"):
        await use_case.execute(_event(TriggerType.TEXT, text=answer))


async def test_request_confirm_exports_lead_to_crm_before_wipe() -> None:
    # Этап 0 CRM: подтверждённая заявка уходит http_request'ом ДО wipe-узлов.
    http = StubHttpClient()
    use_case, port = await _engine(http_client=http)

    await _fill_request_form(use_case)
    await use_case.execute(_click("req_notify"))

    (call,) = [c for c in http.calls if c["url"] == "https://example.invalid/crm/leads"]
    assert call["method"] == "POST"
    assert call["headers"]["Authorization"] == f"Bearer {CRM_KEY}"  # секрет подключения подставлен
    body = call["json_body"]
    assert body["name"] == "Иван"  # интерполяция случилась до стирания переменных
    assert body["contact"] == "+70000000000"
    # Сбоя не было — ⚠️-уведомление админу не отправлялось (только карточка заявки).
    assert len([c for c in port.sent if c.external_chat_id == ADMIN_CHAT]) == 1


async def test_request_crm_failure_notifies_admin_user_path_intact() -> None:
    # Сбой CRM — best-effort: админ получает ⚠️ с данными, пользователь — «Готово».
    failing = StubHttpClient(HttpResponse(status_code=500, json={}, text=""))
    use_case, port = await _engine(http_client=failing)

    await _fill_request_form(use_case)
    await use_case.execute(_click("req_notify"))

    admin_messages = [c for c in port.sent if c.external_chat_id == ADMIN_CHAT]
    assert len(admin_messages) == 2  # карточка заявки + ⚠️ о сбое выгрузки
    assert "не выгружена в CRM" in admin_messages[1].text
    assert "Иван" in admin_messages[1].text  # переменные ещё живы в момент уведомления
    done = port.sent[-1]
    assert done.external_chat_id == CHAT
    assert "Готово" in done.text  # пользовательский путь сбоем CRM не ломается


async def test_developer_contact_delivers_message() -> None:
    use_case, port = await _engine()

    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("dev_start"))  # экран согласия
    await use_case.execute(_click("dev_ask_message"))  # «✅ Согласен — отправить вопрос»
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
    await use_case.execute(_click("req_ask_name"))  # согласие дано
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
    # Guard увёл на перезапуск формы: экран согласия (сбор ПДн — только после него).
    assert "Оформим заявку" in port.sent[-1].text
    assert "разрешаете" in port.sent[-1].text


async def test_form_click_through_with_service_specific_budget_presets() -> None:
    # Фидбэк живого прогона: услуга и бюджет — кнопками, вилки зависят от услуги
    # (из прайс-листа), свою сумму по-прежнему можно вбить текстом.
    use_case, port = await _engine()
    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))
    await use_case.execute(_click("req_ask_name"))  # согласие
    await use_case.execute(_event(TriggerType.TEXT, text="Роман"))
    await use_case.execute(_event(TriggerType.TEXT, text="@roman"))

    assert "Сайт / лендинг" in [b.label for b in port.sent[-1].buttons]  # услуги кнопками
    await use_case.execute(_event(TriggerType.CALLBACK, payload="Чат-бот"))

    assert "1–2 недели" in [b.label for b in port.sent[-1].buttons]  # сроки кнопками
    await use_case.execute(_event(TriggerType.CALLBACK, payload="1–2 недели"))

    # Вилки бюджета — ИМЕННО для чат-бота (от 7 тыс по прайсу), не общие.
    assert next(b.label for b in port.sent[-1].buttons) == "7–15 тыс ₽"
    await use_case.execute(_event(TriggerType.CALLBACK, payload="7–15 тыс ₽"))

    summary = port.sent[-1].text
    assert "Чат-бот" in summary
    assert "1–2 недели" in summary
    assert "7–15 тыс ₽" in summary

    await use_case.execute(_click("req_notify"))
    admin_messages = [c for c in port.sent if c.external_chat_id == ADMIN_CHAT]
    assert len(admin_messages) == 1
    assert "7–15 тыс ₽" in admin_messages[0].text  # выбранная вилка дошла до админа


async def test_typed_task_falls_through_to_generic_budget_presets() -> None:
    use_case, port = await _engine()
    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))
    await use_case.execute(_click("req_ask_name"))
    for answer in ("Иван", "+70000000000", "Нужна интеграция с 1С", "не важно"):
        await use_case.execute(_event(TriggerType.TEXT, text=answer))

    # Своя формулировка услуги -> дефолтные вилки бюджета.
    assert next(b.label for b in port.sent[-1].buttons) == "до 10 тыс ₽"
    await use_case.execute(_event(TriggerType.TEXT, text="12 000 ₽"))  # своя сумма текстом

    assert "12 000 ₽" in port.sent[-1].text  # карточка подтверждения


async def test_cancel_wipes_pii_and_blocks_stale_confirm() -> None:
    # Must-fix роя: «Отменить» обязан стереть собранные ПДн, а протухшая
    # «✅ Подтвердить» после отмены — НЕ отправить отменённую заявку админу.
    use_case, port = await _engine()
    await use_case.execute(_event(TriggerType.START))
    await use_case.execute(_click("req_start"))
    await use_case.execute(_click("req_ask_name"))  # согласие
    for answer in ("Иван", "+70000000000", "Нужен бот", "не важно", "не определён"):
        await use_case.execute(_event(TriggerType.TEXT, text=answer))

    await use_case.execute(_click("req_wipe_cancel"))  # «⬅️ Отменить»
    assert port.sent[-1].text == "Главное меню — чем помочь?"  # вернулись в меню

    await use_case.execute(_click("req_notify"))  # протухшая «✅ Подтвердить»

    assert [c for c in port.sent if c.external_chat_id == ADMIN_CHAT] == []  # отменённая заявка не ушла
    assert "разрешаете" in port.sent[-1].text  # guard увёл на согласие/перезапуск


async def test_stale_dev_confirm_without_data_restarts() -> None:
    use_case, port = await _engine()
    await use_case.execute(_event(TriggerType.START))

    await use_case.execute(_click("dev_notify"))  # протухшая «📨 Отправить» без данных

    assert [c for c in port.sent if c.external_chat_id == DEV_CHAT] == []
    assert "разрешаете" in port.sent[-1].text  # dev-guard увёл на экран согласия


async def test_crafted_callback_cannot_enter_pii_collection() -> None:
    # Негативный пин согласия: callback с payload узла сбора ПДн игнорируется.
    use_case, port = await _engine()
    await use_case.execute(_event(TriggerType.START))
    sent_before = len(port.sent)

    await use_case.execute(_click("req_ask_name"))
    await use_case.execute(_click("dev_ask_message"))

    assert len(port.sent) == sent_before  # оба нажатия молча проигнорированы


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
