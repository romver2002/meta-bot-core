"""Эндпоинт привязки адресата уведомлений (блок notify, ADR-0010)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from application.use_cases.set_notification_target import SetNotificationTargetUseCase
from presentation.api.admin_routes import admin
from presentation.providers.admin import get_set_notification_target_uc
from tests.unit.application.fakes import InMemoryBotRepository, StubNotificationTargets
from tests.unit.factories import make_bot

pytestmark = pytest.mark.unit


async def _build_app() -> tuple[FastAPI, StubNotificationTargets]:
    bots, targets = InMemoryBotRepository(), StubNotificationTargets()
    await bots.save(make_bot("bot-1"))
    app = FastAPI()
    app.include_router(admin, prefix="/api")
    app.dependency_overrides[get_set_notification_target_uc] = lambda: SetNotificationTargetUseCase(
        bots=bots, targets=targets
    )
    return app, targets


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_binds_role_returns_204() -> None:
    app, targets = await _build_app()
    async with _client(app) as client:
        response = await client.put("/api/bots/bot-1/notifications/admin", json={"chat_id": "42"})
    assert response.status_code == 204
    assert targets.stored == {("bot-1", "admin"): "42"}


async def test_unknown_bot_is_404() -> None:
    app, targets = await _build_app()
    async with _client(app) as client:
        response = await client.put("/api/bots/ghost/notifications/admin", json={"chat_id": "42"})
    assert response.status_code == 404
    assert targets.stored == {}


async def test_invalid_role_is_422_and_nothing_stored() -> None:
    app, targets = await _build_app()
    async with _client(app) as client:
        response = await client.put("/api/bots/bot-1/notifications/бо сс!", json={"chat_id": "42"})
    assert response.status_code == 422  # роль вне [A-Za-z0-9_.-]{1,64}
    assert targets.stored == {}


async def test_oversized_chat_id_is_422() -> None:
    app, targets = await _build_app()
    async with _client(app) as client:
        response = await client.put("/api/bots/bot-1/notifications/admin", json={"chat_id": "x" * 129})
    assert response.status_code == 422
    assert targets.stored == {}
