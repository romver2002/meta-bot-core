"""Контракты Pg-репозиториев против реального Postgres 16 (ADR-0008)."""

from __future__ import annotations

import uuid

import pytest

from application.errors import ConcurrencyError
from domain.bot.entities import MiniApp
from domain.bot.value_objects import BotStatus
from domain.flow.codec import flow_to_definition
from domain.flow.entities import Flow, Node
from domain.flow.value_objects import NodeType
from domain.flow.version import FlowVersionStatus
from domain.session.entities import Session
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
