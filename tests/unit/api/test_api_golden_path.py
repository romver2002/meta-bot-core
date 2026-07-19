"""Сквозной контур API на фейках: бот -> сценарий -> публикация -> вебхук -> ответ."""

from __future__ import annotations

import types
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.get_flow_draft import GetFlowDraftUseCase
from application.use_cases.list_bots import ListBotsUseCase
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
    get_get_flow_draft_uc,
    get_list_bots_uc,
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
            get_list_bots_uc: lambda: ListBotsUseCase(bots=bots),
            get_save_flow_draft_uc: lambda: SaveFlowDraftUseCase(bots=bots, flows=flows),
            get_get_flow_draft_uc: lambda: GetFlowDraftUseCase(bots=bots, flows=flows),
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
        assert received.json() == {"ok": True, "outcome": "processed"}  # типизированный исход (enum)
        assert [c.text for c in platform.sent] == ["Привет, !", "Как вас зовут?"]

        # Повторная доставка того же update — дубликат, движок не дёргается.
        duplicate = await client.post(f"/webhooks/telegram/{bot['id']}", json=_start_update())
        assert duplicate.json()["outcome"] == "duplicate"
        assert len(platform.sent) == 2


async def test_connect_same_token_is_idempotent() -> None:
    """BR-009: повторный POST /bots с тем же токеном возвращает существующего бота."""
    app, _, _ = _build_app()
    async with _client(app) as client:
        payload = {"name": "Кофейня", "platform": "telegram", "token": "same-token"}
        first = (await client.post("/api/bots", json=payload)).json()
        second = (await client.post("/api/bots", json=payload)).json()

        assert second["id"] == first["id"]
        listed = (await client.get("/api/bots")).json()["bots"]
        assert [bot["id"] for bot in listed] == [first["id"]]


async def test_list_bots_returns_registry_newest_first_without_tokens() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        empty = await client.get("/api/bots")
        assert empty.status_code == 200
        assert empty.json() == {"bots": []}

        first = (await client.post(
            "/api/bots", json={"name": "Первый", "platform": "telegram", "token": "t1"},
        )).json()
        second = (await client.post(
            "/api/bots", json={"name": "Второй", "platform": "max", "token": "t2"},
        )).json()

        listed = await client.get("/api/bots")
        assert listed.status_code == 200
        bots = listed.json()["bots"]
        assert [bot["id"] for bot in bots] == [second["id"], first["id"]]
        assert bots[0]["platform"] == "max"
        assert bots[0]["status"] == "draft"
        assert all("token" not in bot for bot in bots)  # секреты наружу не отдаются


async def test_webhook_unknown_bot_is_200_not_processed(caplog) -> None:
    # Платформам всегда 200 (иначе ретрай-шторм; MAX отписывает после 8 ч без 200):
    # ApplicationError -> outcome=not_processed + ERROR со стеком в лог.
    import logging

    app, _, _ = _build_app()
    async with _client(app) as client:
        with caplog.at_level(logging.ERROR, logger="app.webhook"):
            response = await client.post("/webhooks/telegram/ghost-bot", json=_start_update())

    assert response.status_code == 200
    assert response.json() == {"ok": True, "outcome": "not_processed"}
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is not None  # стек в логе, не в ответе


async def test_webhook_unsupported_update_is_200_ignored() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        response = await client.post(
            "/webhooks/telegram/any-bot", json={"update_id": 1, "edited_message": {"text": "x"}}
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "outcome": "ignored"}


async def test_save_flow_conflict_returns_409() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Бот", "platform": "max", "token": "fake"})).json()
        definition = flow_to_definition(make_flow("editor-flow"))
        await client.put(f"/api/bots/{bot['id']}/flow", json={"definition": definition})

        # Слепая перезапись без row_version — конфликт (анти-TOCTOU контракт).
        second = await client.put(f"/api/bots/{bot['id']}/flow", json={"definition": definition})
        assert second.status_code == 409


async def test_flow_draft_read_write_roundtrip() -> None:
    """Редактор открывает существующий сценарий и безопасно продолжает его."""
    app, _, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Кофейня", "platform": "telegram", "token": "fake"})).json()
        definition = flow_to_definition(make_flow("editor-flow"))
        saved = (await client.put(f"/api/bots/{bot['id']}/flow", json={"definition": definition})).json()

        loaded = await client.get(f"/api/bots/{bot['id']}/flow")

        assert loaded.status_code == 200
        draft = loaded.json()
        assert draft["definition"] == definition  # раундтрип кодека без искажений
        assert draft["row_version"] == saved["row_version"]
        assert draft["flow_id"] == saved["flow_id"]
        assert draft["name"] == "Кофейня"  # имя по боту, пока редактор не задал своё

        # Прочитанный row_version принимается сохранением — цикл open -> edit -> save.
        resaved = await client.put(
            f"/api/bots/{bot['id']}/flow",
            json={"definition": definition, "row_version": draft["row_version"]},
        )
        assert resaved.status_code == 200
        assert resaved.json()["row_version"] == draft["row_version"] + 1


async def test_flow_draft_before_first_save_is_204() -> None:
    # Машиночитаемое различие: 204 — «бот есть, черновика ещё нет» (чистый лист),
    # 404 — «бота нет». Редактор не парсит detail-строки.
    app, _, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Пустой", "platform": "max", "token": "fake"})).json()
        response = await client.get(f"/api/bots/{bot['id']}/flow")
        assert response.status_code == 204
        assert response.content == b""


async def test_save_without_name_preserves_draft_name() -> None:
    # Сохранение по read-контракту (только definition + row_version) не должно
    # молча сбрасывать имя сценария на bot.name (находка ревью 2026-07-11).
    app, _, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Кофейня", "platform": "telegram", "token": "fake"})).json()
        definition = flow_to_definition(make_flow("editor-flow"))
        await client.put(
            f"/api/bots/{bot['id']}/flow",
            json={"definition": definition, "name": "Приём заявок"},
        )

        await client.put(f"/api/bots/{bot['id']}/flow", json={"definition": definition, "row_version": 0})

        draft = (await client.get(f"/api/bots/{bot['id']}/flow")).json()
        assert draft["name"] == "Приём заявок"  # имя пережило сохранение без name


async def test_flow_draft_of_unknown_bot_is_404() -> None:
    app, _, _ = _build_app()
    async with _client(app) as client:
        response = await client.get("/api/bots/ghost/flow")
        assert response.status_code == 404


async def test_publish_when_platform_unreachable_is_502() -> None:
    # Сеть/TLS до платформы упали при verify_token (живой случай: нет сертификата
    # Минцифры для platform-api2.max.ru) — клиент получает 502, а не голый 500.
    from application.errors import ApplicationError

    app, platform, _ = _build_app()
    async with _client(app) as client:
        bot = (await client.post("/api/bots", json={"name": "Бот", "platform": "telegram", "token": "fake"})).json()
        await client.put(
            f"/api/bots/{bot['id']}/flow",
            json={"definition": flow_to_definition(make_flow("editor-flow"))},
        )
        platform.verify_token_error = ApplicationError("MAX API недоступен для проверки токена")

        response = await client.post(f"/api/bots/{bot['id']}/publish")

        assert response.status_code == 502
        assert "недоступен" in response.json()["detail"]


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
