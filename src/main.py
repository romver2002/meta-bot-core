"""Composition root meta-bot-core.

Единственное место, где слои склеиваются: создание зависимостей, DI,
регистрация платформенных адаптеров в PlatformFactory, маршруты FastAPI.
Только здесь допустимы импорты из всех слоёв сразу
(memory-bank/architecture/overview.md).
"""

from __future__ import annotations

from fastapi import FastAPI

from presentation.api.health_routes import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="meta-bot-core",
        description="Доменное ядро конструктора сценариев чат-ботов и mini app (Telegram, MAX)",
        version="0.1.0",
    )
    app.include_router(health_router)
    # Здесь же по мере появления infrastructure подключаются:
    # - PgFlowRepository / PgSessionRepository / PgBotRepository (ADR-0008),
    # - TelegramBotAdapter / MaxBotAdapter через PlatformFactory (BR-005),
    # - admin_routes (CreateBotUseCase, PublishBotUseCase) и webhook_routes.
    return app


app = create_app()
