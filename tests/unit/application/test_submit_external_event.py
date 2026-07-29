"""SubmitExternalEventUseCase: аутентификация, адресация, payload, идемпотентность (BR-010)."""

from __future__ import annotations

import asyncio

import pytest

from application.errors import (
    BotNotFoundError,
    ExternalEventAuthError,
    ExternalEventValidationError,
)
from application.ports.idempotency import Reservation
from application.use_cases.process_update import UpdateOutcome
from application.use_cases.submit_external_event import (
    ExternalEventOutcome,
    SubmitExternalEventUseCase,
)
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType
from tests.unit.application.fakes import (
    InMemoryBotRepository,
    StubIdempotency,
    StubNotificationTargets,
)
from tests.unit.factories import make_bot

pytestmark = pytest.mark.unit

BOT_ID, TOKEN = "bot-1", "events-token-0123456789abcdef"
OTHER_BOT_ID, OTHER_TOKEN = "bot-2", "events-token-fedcba9876543210"


class StubEventsTokens:
    def __init__(self, tokens: dict[str, str] | None = None) -> None:
        self.tokens = tokens or {}

    async def resolve(self, bot_id: str) -> str | None:
        return self.tokens.get(bot_id)


class SpyEngine:
    """Стоит на месте ProcessUpdateUseCase: записывает поданные события."""

    def __init__(self, outcome: UpdateOutcome = UpdateOutcome.EXECUTED) -> None:
        self.events: list[IncomingEvent] = []
        self.outcome = outcome

    async def execute(self, event: IncomingEvent) -> UpdateOutcome:
        self.events.append(event)
        return self.outcome


def _use_case(
    *,
    with_bot: bool = True,
    tokens: dict[str, str] | None = None,
    targets: dict[str, str] | None = None,
    outcome: UpdateOutcome = UpdateOutcome.EXECUTED,
    idempotency: StubIdempotency | None = None,
    lease_heartbeat_seconds: float = 3600.0,
) -> tuple[SubmitExternalEventUseCase, SpyEngine]:
    bots = InMemoryBotRepository()
    if with_bot:
        bots.storage[BOT_ID] = make_bot(BOT_ID, flow_id="flow-1")
    engine = SpyEngine(outcome)
    use_case = SubmitExternalEventUseCase(
        bots=bots,
        events_tokens=StubEventsTokens(tokens if tokens is not None else {BOT_ID: TOKEN}),
        targets=StubNotificationTargets(targets if targets is not None else {"owner": "chat-owner"}),
        idempotency=idempotency or StubIdempotency(),
        process_update=engine,  # type: ignore[arg-type] — SpyEngine дублирует контракт execute
        lease_heartbeat_seconds=lease_heartbeat_seconds,
    )
    return use_case, engine


async def _submit(use_case: SubmitExternalEventUseCase, **overrides: object) -> ExternalEventOutcome:
    params: dict[str, object] = {
        "provided_token": TOKEN,
        "event": "order_status_changed",
        "role": "owner",
        "chat_id": None,
        "payload": {"title": "Бот"},
        "event_id": None,
    }
    params.update(overrides)
    return await use_case.execute(BOT_ID, **params)  # type: ignore[arg-type]


async def test_happy_path_role_resolves_to_private_chat() -> None:
    use_case, engine = _use_case()

    assert await _submit(use_case) is ExternalEventOutcome.DELIVERED

    (event,) = engine.events
    assert event.event_type is TriggerType.EXTERNAL_EVENT
    assert event.payload == "order_status_changed"
    assert event.external_chat_id == "chat-owner"
    assert event.external_user_id == "chat-owner"  # v1: только личный чат (ADR-0017)
    assert event.variables == {"title": "Бот"}


async def test_user_address_delivers_prefixed_but_identifies_bare() -> None:
    """Адрес доставки и ключ сессии — не одно и то же написание.

    Реестр ролей хранит адрес push-конвенции ``user:<id>`` (иначе на MAX боту
    не написать первым), а вебхук отдаёт тот же id БЕЗ префикса. Если положить
    адрес в идентичность как есть, карточка и нажатие её кнопки окажутся
    в разных сессиях — цепочка молча оборвётся.
    """
    use_case, engine = _use_case(targets={"owner": "user:100000001"})

    assert await _submit(use_case) is ExternalEventOutcome.DELIVERED

    (event,) = engine.events
    assert event.external_chat_id == "user:100000001"  # доставка — по конвенции
    assert event.external_user_id == "100000001"  # сессия — как её видит вебхук


async def test_token_not_set_for_bot_rejected_before_bot_lookup() -> None:
    """Токена у бота нет — отказ до чтения бота (эндпоинт не раскрывает bot_id)."""
    use_case, engine = _use_case(with_bot=False, tokens={})

    with pytest.raises(ExternalEventAuthError):
        await _submit(use_case, provided_token="")
    with pytest.raises(ExternalEventAuthError):
        await _submit(use_case, provided_token="что угодно")
    assert engine.events == []


async def test_wrong_token_rejected_by_comparison() -> None:
    """Токен задан, но не совпал — единственная ветка, где работает
    hmac.compare_digest (в «токен не задан» до сравнения не доходит).
    """
    use_case, engine = _use_case()

    with pytest.raises(ExternalEventAuthError):
        await _submit(use_case, provided_token=TOKEN[:-1] + "x")
    with pytest.raises(ExternalEventAuthError):
        await _submit(use_case, provided_token=TOKEN[:-1])  # префикс — не совпадение
    assert engine.events == []


async def test_token_of_another_bot_does_not_open_this_one() -> None:
    """Токены скоупятся ботом: чужой валидный токен в чужого бота не пускает —
    events-токен одного продукта не даёт писать в бота другого (BR-010).
    """
    use_case, engine = _use_case(tokens={BOT_ID: TOKEN, OTHER_BOT_ID: OTHER_TOKEN})

    with pytest.raises(ExternalEventAuthError):
        await _submit(use_case, provided_token=OTHER_TOKEN)
    assert engine.events == []


async def test_valid_token_but_bot_missing_is_404() -> None:
    use_case, _ = _use_case(with_bot=False)

    with pytest.raises(BotNotFoundError):
        await _submit(use_case)


async def test_unbound_role_is_validation_error() -> None:
    use_case, _ = _use_case(targets={})

    with pytest.raises(ExternalEventValidationError):
        await _submit(use_case, role="ghost")


async def test_exactly_one_of_role_or_chat_id() -> None:
    use_case, _ = _use_case()

    with pytest.raises(ExternalEventValidationError):
        await _submit(use_case, role="owner", chat_id="chat-1")
    with pytest.raises(ExternalEventValidationError):
        await _submit(use_case, role=None, chat_id=None)


async def test_payload_keys_must_be_valid_variable_names() -> None:
    use_case, _ = _use_case()

    with pytest.raises(ExternalEventValidationError):
        await _submit(use_case, payload={"плохой ключ": "x"})
    with pytest.raises(ExternalEventValidationError):
        await _submit(use_case, payload={"ok": "x" * 4001})


async def test_event_id_deduplicates_retries() -> None:
    use_case, engine = _use_case()

    assert await _submit(use_case, event_id="e-1") is ExternalEventOutcome.DELIVERED
    assert await _submit(use_case, event_id="e-1") is ExternalEventOutcome.DUPLICATE  # ретрай вызывающего

    assert len(engine.events) == 1


async def test_failed_delivery_frees_event_id_for_retry() -> None:
    """Сбой платформы не сжигает event_id: ретрай с тем же ключом проходит
    (живой прогон 2026-07-26: 500 от MAX превращал ретрай в ложный «дубль»).
    """
    use_case, engine = _use_case()
    boom = True

    original = engine.execute

    async def flaky(event: IncomingEvent) -> UpdateOutcome:
        nonlocal boom
        if boom:
            boom = False
            raise RuntimeError("платформа упала")
        return await original(event)

    engine.execute = flaky  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await _submit(use_case, event_id="e-retry")
    assert await _submit(use_case, event_id="e-retry") is ExternalEventOutcome.DELIVERED  # ключ освобождён

    assert len(engine.events) == 1


async def test_paused_bot_is_not_reported_as_delivered() -> None:
    """Бот на паузе: событие не исполнено — вызывающему нельзя отвечать «доставлено».

    До ADR-0019 ядро отвечало delivered=true, отправитель помечал карточку
    доставленной, и после снятия паузы она не уходила уже никогда.
    """
    use_case, _ = _use_case(outcome=UpdateOutcome.BOT_NOT_PUBLISHED)

    assert await _submit(use_case, event_id="e-paused") is ExternalEventOutcome.BOT_NOT_PUBLISHED


async def test_unmatched_event_is_not_reported_as_delivered() -> None:
    """В опубликованном сценарии нет триггера под это имя события."""
    use_case, _ = _use_case(outcome=UpdateOutcome.NO_TRIGGER_MATCHED)

    assert await _submit(use_case, event_id="e-nomatch") is ExternalEventOutcome.NO_TRIGGER_MATCHED


@pytest.mark.parametrize("outcome", [UpdateOutcome.BOT_NOT_PUBLISHED, UpdateOutcome.NO_TRIGGER_MATCHED])
async def test_not_executed_event_keeps_event_id_free(outcome: UpdateOutcome) -> None:
    """Не исполнено — ключ свободен: повтор после снятия паузы/починки сценария пройдёт."""
    idempotency = StubIdempotency()
    use_case, _ = _use_case(outcome=outcome, idempotency=idempotency)

    await _submit(use_case, event_id="e-later")
    assert idempotency.state == {}

    healthy, engine = _use_case(idempotency=idempotency)
    assert await _submit(healthy, event_id="e-later") is ExternalEventOutcome.DELIVERED
    assert len(engine.events) == 1


async def test_key_is_only_in_flight_until_delivery_confirms_it() -> None:
    """Ключ продлевается ТОЛЬКО фактическим исполнением (ADR-0019).

    Пока событие в работе, ключ короткоживущий: убьют контейнер — он истечёт
    сам и ретрай пройдёт. После исполнения ключ становится «выполнено» и
    отсекает настоящий дубль.
    """
    idempotency = StubIdempotency()
    use_case, _ = _use_case(idempotency=idempotency)
    seen: list[Reservation] = []

    original = idempotency.confirm

    async def spy_confirm(key: str) -> None:
        seen.append(idempotency.state[key])  # состояние ДО подтверждения
        await original(key)

    idempotency.confirm = spy_confirm  # type: ignore[method-assign]

    await _submit(use_case, event_id="e-confirm")

    assert seen == [Reservation.IN_FLIGHT]
    assert idempotency.state == {f"events:{BOT_ID}:e-confirm": Reservation.DONE}


async def test_parallel_retry_of_in_flight_event_is_not_a_duplicate() -> None:
    """Ретрай, пока первая попытка ещё не завершилась, — «в работе», а не «дубль».

    Отличие принципиальное: «дубль» отправитель считает доставкой, «в работе» —
    поводом повторить позже.
    """
    idempotency = StubIdempotency()
    use_case, _ = _use_case(idempotency=idempotency)
    idempotency.state[f"events:{BOT_ID}:e-busy"] = Reservation.IN_FLIGHT

    assert await _submit(use_case, event_id="e-busy") is ExternalEventOutcome.IN_FLIGHT


async def test_cancelled_delivery_frees_event_id() -> None:
    """Отмена задачи (разрыв соединения, shutdown) — не Exception: ключ всё равно
    освобождается, иначе карточка исчезает навсегда при graceful shutdown.
    """
    idempotency = StubIdempotency()
    use_case, engine = _use_case(idempotency=idempotency)

    async def cancelled(event: IncomingEvent) -> UpdateOutcome:
        raise asyncio.CancelledError

    engine.execute = cancelled  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await _submit(use_case, event_id="e-cancel")
    assert idempotency.state == {}


async def test_release_survives_cancellation_mid_forget() -> None:
    """Отмена приходит, пока forget уже стартовал: shield доводит удаление до конца.

    Без shield ключ остался бы «в работе» до истечения TTL, и ретрай вызывающего
    вернул бы in_flight вместо доставки.
    """
    idempotency = StubIdempotency()
    use_case, engine = _use_case(idempotency=idempotency)
    forget_started, allow_forget = asyncio.Event(), asyncio.Event()
    original_forget = idempotency.forget

    async def slow_forget(key: str) -> None:
        forget_started.set()
        await allow_forget.wait()
        await original_forget(key)

    async def failing(event: IncomingEvent) -> UpdateOutcome:
        raise RuntimeError("платформа упала")

    idempotency.forget = slow_forget  # type: ignore[method-assign]
    engine.execute = failing  # type: ignore[method-assign]

    task = asyncio.create_task(_submit(use_case, event_id="e-shield"))
    await forget_started.wait()
    task.cancel()
    allow_forget.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert idempotency.state == {}


async def test_lease_is_renewed_while_execution_is_running() -> None:
    """Долгое исполнение продлевает аренду ключа, а не даёт ей истечь под собой."""
    idempotency = StubIdempotency()
    use_case, engine = _use_case(idempotency=idempotency, lease_heartbeat_seconds=0.01)
    renewed, release = asyncio.Event(), asyncio.Event()
    original_touch, original_execute = idempotency.touch, engine.execute

    async def spy_touch(key: str) -> None:
        await original_touch(key)
        renewed.set()

    async def slow(event: IncomingEvent) -> UpdateOutcome:
        await release.wait()
        return await original_execute(event)

    idempotency.touch = spy_touch  # type: ignore[method-assign]
    engine.execute = slow  # type: ignore[method-assign]

    task = asyncio.create_task(_submit(use_case, event_id="e-slow"))
    await renewed.wait()
    release.set()

    assert await task is ExternalEventOutcome.DELIVERED
    touched_during_run = len(idempotency.touched)
    await asyncio.sleep(0.05)  # heartbeat остановлен вместе с исполнением
    assert len(idempotency.touched) == touched_during_run
    assert idempotency.state == {f"events:{BOT_ID}:e-slow": Reservation.DONE}


async def test_broken_dedup_store_does_not_cancel_a_real_delivery() -> None:
    """Карточка уже ушла: сбой confirm нельзя превращать в ошибку вызывающему —
    он повторит событие, и получатель увидит её дважды.
    """
    idempotency = StubIdempotency()
    use_case, engine = _use_case(idempotency=idempotency)

    async def broken_confirm(key: str) -> None:
        raise RuntimeError("redis недоступен")

    idempotency.confirm = broken_confirm  # type: ignore[method-assign]

    assert await _submit(use_case, event_id="e-broken") is ExternalEventOutcome.DELIVERED
    assert len(engine.events) == 1
