"""E2E-контур авторизации mini app через эндпоинт с РЕАЛЬНЫМ адаптером (BR-007)."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

import httpx
import pytest
from fastapi import FastAPI

from application.use_cases.attach_mini_app import AttachMiniAppUseCase
from application.use_cases.authenticate_mini_app import AuthenticateMiniAppUseCase
from domain.bot.entities import Bot
from domain.bot.value_objects import Platform, Token
from infrastructure.platforms.factory import RegistryPlatformFactory
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter
from presentation.api.admin_routes import admin
from presentation.providers.admin import get_attach_mini_app_uc, get_authenticate_mini_app_uc
from tests.unit.application.fakes import InMemoryBotRepository, InMemoryTokenVault

pytestmark = pytest.mark.unit

TOKEN = "12345:test-token"


def _signed(token: str, params: dict[str, str]) -> str:
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**params, "hash": digest})


async def _build_app() -> FastAPI:
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    bot = Bot(
        id="bot-1",
        name="B",
        platform=Platform.TELEGRAM,
        token=Token(vault_ref=await vault.store("bot-1", TOKEN)),
    )
    await bots.save(bot)
    # init_data_max_age=0 → проверку свежести отключаем (auth_date в тесте фиксирован).
    factory = RegistryPlatformFactory({Platform.TELEGRAM: TelegramBotAdapter(httpx.AsyncClient(), init_data_max_age=0)})
    app = FastAPI()
    app.include_router(admin, prefix="/api")
    app.dependency_overrides[get_authenticate_mini_app_uc] = lambda: AuthenticateMiniAppUseCase(
        bots=bots, token_vault=vault, platform_factory=factory
    )
    app.dependency_overrides[get_attach_mini_app_uc] = lambda: AttachMiniAppUseCase(bots=bots)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_valid_init_data_authenticates_end_to_end() -> None:
    app = await _build_app()
    init_data = _signed(TOKEN, {"auth_date": "1700000000", "user": json.dumps({"id": 777, "first_name": "Роман"})})
    async with _client(app) as client:
        response = await client.post("/api/bots/bot-1/miniapp/auth", json={"init_data": init_data})
    assert response.status_code == 200
    assert response.json()["external_user_id"] == "777"


async def test_tampered_init_data_is_401() -> None:
    app = await _build_app()
    init_data = _signed(TOKEN, {"auth_date": "1700000000", "user": '{"id":777}'}) + "&x=tamper"
    async with _client(app) as client:
        response = await client.post("/api/bots/bot-1/miniapp/auth", json={"init_data": init_data})
    assert response.status_code == 401


async def test_wrong_token_signature_is_401() -> None:
    app = await _build_app()
    init_data = _signed("999:other-token", {"auth_date": "1700000000", "user": '{"id":1}'})
    async with _client(app) as client:
        response = await client.post("/api/bots/bot-1/miniapp/auth", json={"init_data": init_data})
    assert response.status_code == 401


async def test_attach_mini_app_https_ok() -> None:
    app = await _build_app()
    async with _client(app) as client:
        response = await client.put(
            "/api/bots/bot-1/miniapp", json={"url": "https://shop.example.com", "title": "Витрина"}
        )
    assert response.status_code == 200
    assert response.json()["id"] == "bot-1"


async def test_attach_mini_app_non_https_is_422() -> None:
    app = await _build_app()
    async with _client(app) as client:
        response = await client.put("/api/bots/bot-1/miniapp", json={"url": "http://insecure.example.com"})
    assert response.status_code == 422
