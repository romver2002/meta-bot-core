"""Composition root meta-bot-core.

Единственное место, где слои склеиваются: создание зависимостей, DI
(dependency_overrides провайдеров presentation), регистрация платформенных
адаптеров в PlatformFactory, маршруты FastAPI. Только здесь допустимы импорты
из всех слоёв сразу (memory-bank/architecture/overview.md).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from application.system.use_cases.get_healthcheck import GetHealthcheckUseCase, get_app_version
from application.system.use_cases.get_services_healthcheck import GetServicesHealthcheckUseCase
from infrastructure.config import Settings
from infrastructure.integrations.health_checks import (
    InfraHealthServiceProbe,
    SettingsHealthServiceRegistry,
)
from presentation.api.health_routes import health
from presentation.providers.system import get_healthcheck_uc, get_services_healthcheck_uc

MSK = timezone(timedelta(hours=3))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.startup_time_service = datetime.now(tz=MSK)
    yield


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="meta-bot-core",
        description="Доменное ядро конструктора сценариев чат-ботов и mini app (Telegram, MAX)",
        version=get_app_version("meta-bot-core"),
        lifespan=lifespan,
    )
    app.include_router(health, prefix="/healthchecks", tags=["Состояние"])

    # DI провайдеров presentation — здесь, чтобы presentation не импортировал
    # infrastructure (контракт .importlinter).
    app.dependency_overrides[get_healthcheck_uc] = lambda: GetHealthcheckUseCase(
        project_name=settings.project_name,
        url=settings.public_url,
    )
    app.dependency_overrides[get_services_healthcheck_uc] = lambda: GetServicesHealthcheckUseCase(
        registry=SettingsHealthServiceRegistry(settings),
        probe=InfraHealthServiceProbe(settings),
    )

    # Здесь же по мере появления infrastructure подключаются:
    # - PgFlowRepository / PgSessionRepository / PgBotRepository (ADR-0008),
    # - TelegramBotAdapter / MaxBotAdapter через PlatformFactory (BR-005),
    # - admin_routes (CreateBotUseCase, PublishBotUseCase) и webhook_routes.
    return app


app = create_app()
