"""CORS-политика браузерных web-клиентов meta-bot-core."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def add_cors_middleware(app: FastAPI, *, allowed_origins: Sequence[str]) -> None:
    """Разрешает JSON POST только точным origin'ам из конфигурации."""
    if not allowed_origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )
