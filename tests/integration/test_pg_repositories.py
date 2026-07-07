"""Контракты Pg-репозиториев против реального Postgres 16 (ADR-0008)."""

from __future__ import annotations

import uuid

import pytest

from application.errors import ConcurrencyError
from domain.bot.entities import MiniApp
from domain.bot.value_objects import BotStatus
from domain.flow.version import FlowVersionStatus
from domain.session.entities import Session
from infrastructure.db.mappers import flow_to_definition
from infrastructure.db.repositories import PgBotRepository, PgFlowRepository, PgSessionRepository
from tests.unit.factories import make_bot, make_flow

pytestmark = pytest.mark.integration


def _uid() -> str:
    return uuid.uuid4().hex


async def test_flow_draft_roundtrip_and_optimistic_lock(session_factory) -> None:
    repo = PgFlowRepository(session_factory)
    flow = make_flow(_uid())

    assert await repo.save_draft(flow) == 0
    loaded = await repo.get_draft(flow.id)
    assert loaded is not None
    assert flow_to_definition(loaded) == flow_to_definition(flow)
    assert loaded.name == flow.name

    assert await repo.save_draft(flow, expected_row_version=0) == 1
    with pytest.raises(ConcurrencyError):
        await repo.save_draft(flow, expected_row_version=0)


async def test_flow_publish_freezes_immutable_versions(session_factory) -> None:
    repo = PgFlowRepository(session_factory)
    flow = make_flow(_uid())
    await repo.save_draft(flow)

    first = await repo.publish(flow.id)
    assert first.version == 1
    assert first.status is FlowVersionStatus.PUBLISHED

    # Черновик живёт дальше и публикуется повторно новой версией.
    assert await repo.get_draft(flow.id) is not None
    second = await repo.publish(flow.id)
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


async def test_session_single_active_per_user(session_factory) -> None:
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
