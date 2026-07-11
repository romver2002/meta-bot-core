"""Мидлварь наблюдаемости (ADR-0013): request_id сквозной, единый JSON-500."""

from __future__ import annotations

import logging

import httpx
import pytest
from fastapi import FastAPI

from presentation.middleware.request_context import request_context_middleware

pytestmark = pytest.mark.unit


def _build_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_context_middleware)

    @app.get("/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("необработанное")

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_incoming_request_id_is_propagated_to_response() -> None:
    async with _client(_build_app()) as client:
        response = await client.get("/ok", headers={"X-Request-ID": "client-42"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-42"


async def test_request_id_is_generated_when_absent() -> None:
    async with _client(_build_app()) as client:
        response = await client.get("/ok")
    assert response.headers["X-Request-ID"]  # непустой сгенерированный id


async def test_unhandled_exception_becomes_json_500_with_request_id(caplog: pytest.LogCaptureFixture) -> None:
    async with _client(_build_app()) as client:
        with caplog.at_level(logging.ERROR, logger="app.http"):
            response = await client.get("/boom", headers={"X-Request-ID": "err-7"})

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Внутренняя ошибка сервера"  # стек наружу не отдаём
    assert body["request_id"] == "err-7"  # клиенту есть что назвать при обращении
    assert response.headers["X-Request-ID"] == "err-7"
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1  # залогировано ровно один раз, со стеком
    assert errors[0].exc_info is not None
