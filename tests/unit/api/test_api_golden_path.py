"""Сквозной контур API на фейках: бот -> сценарий -> публикация -> вебхук -> ответ."""

from __future__ import annotations

import types
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.process_update import ProcessUpdateUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from domain.flow.codec import flow_to_definition
from infrastructure.platforms.telegram.webhook import parse_telegram_update
from presentation.api.admin_routes import admin
from presentation.api.webhook_routes import webhooks
from presentation.providers.admin import (
    get_create_bot_uc,
    get_get_bot_uc,
    get_publish_bot_uc,
    get_save_flow_draft_uc,
)
from presentation.providers.webhooks import (
    get_idempotency,
    get_platform_factory,
    get_process_update_uc,
)
from tests.unit.application.fakes import (
    InMemoryBotRepository,
    InMemoryFlowRepository,
    InMemorySessionRepository,
    InMemoryTokenVault,
    StubHttpClient,
    StubIdempotency,
    StubNotificationTargets,
    StubPlatform,
    StubPlatformFactory,
    StubSecretResolver,
)
from tests.unit.factories import full_capabilities, make_flow

pytestmark = pytest.mark.unit


def _build_app() -> tuple[FastAPI, StubPlatform, StubIdempotency]:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    sessions, vault = InMemorySessionRepository(), InMemoryTokenVault()
    platform = StubPlatform(full_capabilities(), parser=parse_telegram_update)
    factory = StubPlatformFactory(platform)
    idempotency = StubIdempotency()

    app = FastAPI()
    app.state.settings = types.SimpleNamespace(webhook_secret=None)
    app.include_router(admin, prefix="/api")
    app.include_router(webhooks, prefix="/webhooks")
    app.dependency_overrides.update(
        {
            get_create_bot_uc: lambda: CreateBotUseCase(bots=bots, token_vault=vault),
            get_get_bot_uc: lambda: GetBotUseCase(bots=bots),
            get_save_flow_draft_uc: lambda: SaveFlowDraftUseCase(bots=bots, flows=flows),
            get_publish_bot_uc: lambda: PublishBotUseCase(
                bots=bots, flows=flows, token_vault=vault, platform_factory=factory
            ),
            get_platform_factory: lambda: factory,
            get_idempotency: lambda: idempotency,
            get_process_update_uc: lambda: ProcessUpdateUseCase(
                bots=bots,
                flows=flows,
                sessions=sessions,
                token_vault=vault,
                platform_factory=factory,
                http_client=StubHttpClient(),
                secrets=StubSecretResolver(),
                notifications=StubNotificationTargets(),
            ),
        }
    )
    return app, platform, idempotency


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _start_update(update_id: int = 111) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {"text": "/start", "from": {"id": 42}, "chat": {"id": 4242}},
    }


async def test_golden_path_from_create_to_bot_reply() -> None:
    app, platform, _ = _build_app()
    async with _client(app) as client:
        created = await client.post(
            "/api/bots",
            json={"name": "Кофейня", "platform": "telegram", "token": "fake-token"},
        )
        assert created.status_code == 201
        bot = created.json()
        assert bot["status"] == "draft"
        assert "token" not in bot  # секрет наружу не возвращается

        saved = await client.put(
            f"/api/bots/{bot['id']}/flow",
            json={"definition": flow_to_definition(make_flow("editor-flow")), "row_version": None},
        )
        assert saved.status_code == 200
        assert saved.json()["row_version"] == 0

        published = await client.post(f"/api/bots/{bot['id']}/publish")
        assert published.status_code == 200
        assert published.json()["bot"]["status"] == "published"

        received = await client.post(f"/webhooks/telegram/{bot['id']}", json=_start_update())
        assert received.json() == {"ok": True}
        assert [c.text for c in platform.sent] == ["Привет, !", "Как вас зовут?"]

        # Повторная доставка того же update — дубликат, движок не дёргается.
        duplicate = await client.post(f"/webhooks/telegram/{bot['id']}", json=_start_update())
        assert duplicate.json()["duplicate"] is True
        assert len(platform.sent) == 2


async def test_save_flow_conflict_returns_409() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Бот", "platform": "max", "token": "fake"})).json()
        definition = flow_to_definition(make_flow("editor-flow"))
        await client.put(f"/api/bots/{bot['id']}/flow", json={"definition": definition})

        # Слепая перезапись без row_version — конфликт (анти-TOCTOU контракт).
        second = await client.put(f"/api/bots/{bot['id']}/flow", json={"definition": definition})
        assert second.status_code == 409


async def test_publish_bot_without_flow_is_404() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Пустой", "platform": "telegram", "token": "fake"})).json()
        response = await client.post(f"/api/bots/{bot['id']}/publish")
        assert response.status_code == 404


async def test_unknown_platform_is_404() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        response = await client.post("/webhooks/viber/some-bot", json={})
        assert response.status_code == 404
