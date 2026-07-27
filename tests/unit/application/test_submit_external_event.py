"""SubmitExternalEventUseCase: аутентификация, адресация, payload, идемпотентность (BR-010)."""

from __future__ import annotations

import pytest

from application.errors import (
    BotNotFoundError,
    ExternalEventAuthError,
    ExternalEventValidationError,
)
from application.use_cases.submit_external_event import SubmitExternalEventUseCase
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

    def __init__(self) -> None:
        self.events: list[IncomingEvent] = []

    async def execute(self, event: IncomingEvent) -> None:
        self.events.append(event)


def _use_case(
    *,
    with_bot: bool = True,
    tokens: dict[str, str] | None = None,
    targets: dict[str, str] | None = None,
) -> tuple[SubmitExternalEventUseCase, SpyEngine]:
    bots = InMemoryBotRepository()
    if with_bot:
        bots.storage[BOT_ID] = make_bot(BOT_ID, flow_id="flow-1")
    engine = SpyEngine()
    use_case = SubmitExternalEventUseCase(
        bots=bots,
        events_tokens=StubEventsTokens(tokens if tokens is not None else {BOT_ID: TOKEN}),
        targets=StubNotificationTargets(targets if targets is not None else {"owner": "chat-owner"}),
        idempotency=StubIdempotency(),
        process_update=engine,  # type: ignore[arg-type] — SpyEngine дублирует контракт execute
    )
    return use_case, engine


async def _submit(use_case: SubmitExternalEventUseCase, **overrides: object) -> bool:
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

    assert await _submit(use_case) is True

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

    assert await _submit(use_case) is True

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

    assert await _submit(use_case, event_id="e-1") is True
    assert await _submit(use_case, event_id="e-1") is False  # ретрай вызывающего

    assert len(engine.events) == 1


async def test_failed_delivery_frees_event_id_for_retry() -> None:
    """Сбой платформы не сжигает event_id: ретрай с тем же ключом проходит
    (живой прогон 2026-07-26: 500 от MAX превращал ретрай в ложный «дубль»).
    """
    use_case, engine = _use_case()
    boom = True

    original = engine.execute

    async def flaky(event: IncomingEvent) -> None:
        nonlocal boom
        if boom:
            boom = False
            raise RuntimeError("платформа упала")
        await original(event)

    engine.execute = flaky  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await _submit(use_case, event_id="e-retry")
    assert await _submit(use_case, event_id="e-retry") is True  # ключ освобождён

    assert len(engine.events) == 1
