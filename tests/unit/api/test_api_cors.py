"""CORS для браузерного mini app (ADR-0006): точные origin'ы, по умолчанию выключен.

Проверяется проводка composition root: CORS_ALLOWED_ORIGINS -> CORSMiddleware.
Сама валидация значений (без wildcard/path) — валидатор Settings.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from infrastructure.config import Settings
from main import create_app
from presentation.middleware.cors import add_cors_middleware
from presentation.middleware.request_context import request_context_middleware

pytestmark = pytest.mark.unit

PREFLIGHT_HEADERS = {
    "Origin": "https://miniapp.example",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "Content-Type",
}


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test")


async def test_preflight_allows_configured_miniapp_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://miniapp.example"]')
    async with _client(create_app()) as client:
        response = await client.options("/api/bots/bot-1/miniapp/auth", headers=PREFLIGHT_HEADERS)

    assert response.status_code == httpx.codes.OK
    assert response.headers["access-control-allow-origin"] == "https://miniapp.example"
    assert "POST" in response.headers["access-control-allow-methods"]


async def test_preflight_rejects_foreign_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://miniapp.example"]')
    async with _client(create_app()) as client:
        response = await client.options(
            "/api/bots/bot-1/miniapp/auth",
            headers={**PREFLIGHT_HEADERS, "Origin": "https://evil.example"},
        )

    assert response.status_code == httpx.codes.BAD_REQUEST
    assert "access-control-allow-origin" not in response.headers


async def test_cors_disabled_without_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    # Пустой список = CORS выключен; setenv, а не delenv, — иначе create_app()
    # прочитал бы .env разработчика и тест стал бы негерметичным.
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "[]")
    async with _client(create_app()) as client:
        response = await client.options("/api/bots/bot-1/miniapp/auth", headers=PREFLIGHT_HEADERS)

    # Middleware не подключён вовсе: браузерный preflight не обслуживается.
    assert response.status_code == httpx.codes.METHOD_NOT_ALLOWED
    assert "access-control-allow-origin" not in response.headers


async def test_cors_wraps_unified_error_response() -> None:
    app = FastAPI()
    app.middleware("http")(request_context_middleware)
    add_cors_middleware(app, allowed_origins=("https://miniapp.example",))

    @app.post("/boom")
    async def boom() -> None:
        raise RuntimeError("internal detail must stay on the server")

    async with _client(app) as client:
        response = await client.post("/boom", headers={"Origin": "https://miniapp.example"})

    assert response.status_code == httpx.codes.INTERNAL_SERVER_ERROR
    assert response.headers["access-control-allow-origin"] == "https://miniapp.example"
    assert response.headers["access-control-expose-headers"] == "X-Request-ID"
    assert "access-control-allow-credentials" not in response.headers


def test_settings_parse_cors_origins_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        '["https://mini.example","http://127.0.0.1:5174"]',
    )

    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origins == (
        "https://mini.example",
        "http://127.0.0.1:5174",
    )


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "ftp://mini.example",
        "https://mini.example/",
        "https://mini.example/path",
        "https://user@mini.example",
    ],
)
def test_settings_reject_non_exact_cors_origin(origin: str) -> None:
    with pytest.raises(ValidationError, match="CORS origin"):
        Settings(cors_allowed_origins=(origin,), _env_file=None)


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("https://MINI.EXAMPLE", "https://mini.example"),
        ("HTTPS://mini.example", "https://mini.example"),
        ("https://mini.example:443", "https://mini.example"),
        ("http://localhost:80", "http://localhost"),
        ("https://пример.рф", "https://xn--e1afmkfd.xn--p1ai"),
        ("https://mini.example:8443", "https://mini.example:8443"),
    ],
)
def test_settings_canonicalize_cors_origin(raw: str, canonical: str) -> None:
    # Браузер шлёт Origin в нижнем регистре, IDN в punycode, дефолтный порт опускает;
    # Starlette сравнивает строго — конфиг канонизируем, иначе origin молча не совпал бы.
    settings = Settings(cors_allowed_origins=(raw,), _env_file=None)
    assert settings.cors_allowed_origins == (canonical,)


@pytest.mark.parametrize("secret", ["wh-s3cret", "ABCDE", "a" * 256])
def test_settings_accept_valid_webhook_secret(secret: str) -> None:
    assert Settings(webhook_secret=secret, _env_file=None).webhook_secret == secret


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_settings_empty_webhook_secret_is_none(raw: str | None) -> None:
    # Пустая строка из env (compose ${WEBHOOK_SECRET:-}) = «не задано» -> None,
    # иначе валидатор ронял бы старт api (баг, пойманный живым прогоном 2026-07-12).
    assert Settings(webhook_secret=raw, _env_file=None).webhook_secret is None


@pytest.mark.parametrize("secret", ["abcd", "has_underscore", "bad!char", "a" * 257])
def test_settings_reject_invalid_webhook_secret(secret: str) -> None:
    # С ADR-0014 секрет уходит платформам: недопустимый символ/длина навсегда
    # ломали бы регистрацию вебхука — ловим на старте, не в 502 от платформы.
    with pytest.raises(ValidationError, match="WEBHOOK_SECRET"):
        Settings(webhook_secret=secret, _env_file=None)
