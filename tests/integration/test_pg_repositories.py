"""Контракты Pg-репозиториев против реального Postgres 16 (ADR-0008)."""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa

from application.errors import BotCreationError, ConcurrencyError
from domain.bot.entities import MiniApp
from domain.bot.value_objects import BotStatus, Token
from domain.flow.codec import flow_to_definition
from domain.flow.entities import Flow, Node
from domain.flow.value_objects import NodeType
from domain.flow.version import FlowVersionStatus
from domain.session.entities import Session
from infrastructure.db.models import BotModel
from infrastructure.db.repositories import PgBotRepository, PgFlowRepository, PgSessionRepository
from tests.unit.factories import make_bot, make_flow

pytestmark = pytest.mark.integration


def _uid() -> str:
    return uuid.uuid4().hex


def _with_extra_node(flow: Flow) -> Flow:
    """Копия сценария с дополнительным блоком — другой content_hash."""
    extra = Node(id="extra", type=NodeType.SEND_MESSAGE, params={"text": "Дополнение"})
    return Flow(
        id=flow.id,
        name=flow.name,
        nodes={**flow.nodes, "extra": extra},
        triggers=flow.triggers,
        transitions=flow.transitions,
    )


async def test_flow_draft_roundtrip_and_optimistic_lock(session_factory) -> None:
    repo = PgFlowRepository(session_factory)
    flow = make_flow(_uid())

    assert await repo.save_draft(flow, expected_row_version=None) == 0
    draft = await repo.get_draft(flow.id)
    assert draft is not None
    assert flow_to_definition(draft.flow) == flow_to_definition(flow)
    assert draft.row_version == 0

    # Слепая перезапись (без токена конкуренции) запрещена.
    with pytest.raises(ConcurrencyError):
        await repo.save_draft(flow, expected_row_version=None)

    assert await repo.save_draft(flow, expected_row_version=0) == 1
    with pytest.raises(ConcurrencyError):
        await repo.save_draft(flow, expected_row_version=0)


async def test_flow_publish_is_guarded_and_idempotent(session_factory) -> None:
    repo = PgFlowRepository(session_factory)
    flow = make_flow(_uid())
    bot_id = _uid()
    await repo.save_draft(flow, expected_row_version=None)

    first = await repo.publish(flow.id, expected_row_version=0, bot_id=bot_id)
    assert first.version == 1
    assert first.status is FlowVersionStatus.PUBLISHED

    # Идемпотентный ретрай: неизменённый черновик -> та же версия, не сирота.
    retry = await repo.publish(flow.id, expected_row_version=0, bot_id=bot_id)
    assert retry.id == first.id

    # Анти-TOCTOU: чужой row_version не публикуется.
    with pytest.raises(ConcurrencyError):
        await repo.publish(flow.id, expected_row_version=41, bot_id=bot_id)

    # Изменённый черновик публикуется следующей версией.
    assert await repo.save_draft(_with_extra_node(flow), expected_row_version=0) == 1
    second = await repo.publish(flow.id, expected_row_version=1, bot_id=bot_id)
    assert second.version == 2

    frozen = await repo.get_version(first.id)
    assert frozen is not None
    assert flow_to_definition(frozen.flow) == flow_to_definition(flow)

    versions = await repo.list_versions(flow.id)
    assert len(versions) == 3  # draft + v1 + v2


async def test_bot_roundtrip_with_mini_app(session_factory) -> None:
    repo = PgBotRepository(session_factory)
    bot = make_bot(_uid(), flow_id=_uid())
    bot.mini_app = MiniApp(id=_uid(), bot_id=bot.id, url="https://shop.example.com", title="Витрина")

    await repo.save(bot)
    loaded = await repo.get(bot.id)
    assert loaded is not None
    assert (loaded.id, loaded.name, loaded.platform) == (bot.id, bot.name, bot.platform)
    assert loaded.status is BotStatus.DRAFT
    assert loaded.token.vault_ref == bot.token.vault_ref
    assert loaded.mini_app is not None
    assert loaded.mini_app.url == "https://shop.example.com"

    loaded.publish(flow=make_flow(bot.flow_id or ""), token_is_valid=True)
    await repo.save(loaded)
    republished = await repo.get(bot.id)
    assert republished is not None
    assert republished.status is BotStatus.PUBLISHED


async def test_token_fingerprint_lookup_and_race(session_factory) -> None:
    """BR-009: поиск по отпечатку токена + уникальный индекс закрывает гонку connect."""
    repo = PgBotRepository(session_factory)
    fingerprint = "a" * 64
    original = make_bot(_uid(), flow_id=_uid())
    original.token = Token(vault_ref=original.token.vault_ref, fingerprint=fingerprint)
    await repo.save(original)

    found = await repo.find_by_token_fingerprint(fingerprint)
    assert found is not None
    assert found.id == original.id
    assert found.token.fingerprint == fingerprint
    assert await repo.find_by_token_fingerprint("b" * 64) is None

    racer = make_bot(_uid(), flow_id=_uid())
    racer.token = Token(vault_ref=racer.token.vault_ref, fingerprint=fingerprint)
    with pytest.raises(BotCreationError):
        await repo.save(racer)


async def test_list_all_returns_newest_first_with_mini_app(session_factory) -> None:
    repo = PgBotRepository(session_factory)
    older, newer = make_bot(_uid(), flow_id=_uid()), make_bot(_uid(), flow_id=_uid())
    newer.mini_app = MiniApp(id=_uid(), bot_id=newer.id, url="https://list.example.com", title="Реестр")
    await repo.save(older)
    await repo.save(newer)

    # created_at задаётся явно: контракт «новые первыми» проверяется по времени
    # создания, а не по случайному порядку вставки/микросекундам now().
    base = datetime.datetime.now(tz=datetime.UTC)
    async with session_factory() as db, db.begin():
        for bot_id, created in ((older.id, base - datetime.timedelta(days=1)), (newer.id, base)):
            await db.execute(
                sa.update(BotModel).where(BotModel.id == uuid.UUID(bot_id)).values(created_at=created)
            )

    listed = await repo.list_all()
    assert [bot.id for bot in listed] == [newer.id, older.id]
    assert listed[0].mini_app is not None
    assert listed[0].mini_app.url == "https://list.example.com"
    assert listed[1].mini_app is None


async def test_session_single_active_per_user_and_completion(session_factory) -> None:
    repo = PgSessionRepository(session_factory)
    bot_id, user = _uid(), "ext-user-1"
    session = Session(id=_uid(), bot_id=bot_id, external_user_id=user, current_node_id="greet")
    session.remember("name", "Роман")
    await repo.save(session)

    active = await repo.get_active(bot_id, user)
    assert active is not None
    assert active.current_node_id == "greet"
    assert active.variables == {"name": "Роман"}

    duplicate = Session(id=_uid(), bot_id=bot_id, external_user_id=user)
    with pytest.raises(ConcurrencyError):
        await repo.save(duplicate)

    # Завершение освобождает пару (Bot, user): новая сессия создаётся без конфликта.
    active.complete()
    await repo.save(active)
    assert await repo.get_active(bot_id, user) is None
    fresh = Session(id=_uid(), bot_id=bot_id, external_user_id=user)
    await repo.save(fresh)
    refreshed = await repo.get_active(bot_id, user)
    assert refreshed is not None
    assert refreshed.id == fresh.id


async def test_session_retention_expires_idle_and_deletes_finished(session_factory) -> None:
    """Ретеншен ПДн (BR-008): зависшие FSM просрочиваются со стиранием переменных,
    завершённые старше срока хранения удаляются целиком (вместе с user/chat id).
    """
    import datetime as dt

    import sqlalchemy as sa

    from infrastructure.db.models import SessionModel

    repo = PgSessionRepository(session_factory)
    bot_id = _uid()
    now = dt.datetime.now(dt.UTC)

    idle = Session(id=_uid(), bot_id=bot_id, external_user_id="u-idle")
    idle.remember("req_contact", "+70000000000")  # ПДн, которые обязаны стереться
    await repo.save(idle)
    finished = Session(id=_uid(), bot_id=bot_id, external_user_id="u-done")
    finished.complete()
    await repo.save(finished)
    fresh = Session(id=_uid(), bot_id=bot_id, external_user_id="u-fresh")
    await repo.save(fresh)

    # Состариваем idle и finished: last_event_at — критерий простоя (штампуется
    # мапперами на каждый save), updated_at — критерий срока хранения.
    async with session_factory() as db, db.begin():
        await db.execute(
            sa.update(SessionModel)
            .where(SessionModel.id.in_([uuid.UUID(idle.id), uuid.UUID(finished.id)]))
            .values(
                updated_at=now - dt.timedelta(days=40),
                last_event_at=now - dt.timedelta(days=40),
            )
        )

    assert await repo.expire_idle(now - dt.timedelta(hours=1)) == 1  # fresh не тронут
    assert await repo.get_active(bot_id, "u-idle") is None  # пара (Bot, user) освобождена
    async with session_factory() as db:
        idle_model = await db.get(SessionModel, uuid.UUID(idle.id))
        assert idle_model is not None
        assert idle_model.variables == {}  # ПДн стёрты немедленно, не дожидаясь удаления

    assert await repo.delete_finished_before(now - dt.timedelta(days=30)) == 1
    async with session_factory() as db:
        assert await db.get(SessionModel, uuid.UUID(finished.id)) is None  # строка стёрта целиком
        # Свежепросроченная idle-сессия ждёт свой срок хранения (уже без переменных).
        assert await db.get(SessionModel, uuid.UUID(idle.id)) is not None
        assert await db.get(SessionModel, uuid.UUID(fresh.id)) is not None
