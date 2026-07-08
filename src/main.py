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

import httpx
from fastapi import FastAPI

from application.system.use_cases.get_healthcheck import GetHealthcheckUseCase, get_app_version
from application.system.use_cases.get_services_healthcheck import GetServicesHealthcheckUseCase
from application.use_cases.authenticate_mini_app import AuthenticateMiniAppUseCase
from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.process_update import ProcessUpdateUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from domain.bot.value_objects import Platform
from infrastructure.cache.redis_idempotency import RedisIdempotency
from infrastructure.config import Settings
from infrastructure.db.engine import build_engine, build_session_factory
from infrastructure.db.repositories import PgBotRepository, PgFlowRepository, PgSessionRepository
from infrastructure.integrations.health_checks import (
    InfraHealthServiceProbe,
    SettingsHealthServiceRegistry,
)
from infrastructure.platforms.factory import RegistryPlatformFactory
from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter
from infrastructure.security.file_token_vault import FileTokenVault
from presentation.api.admin_routes import admin
from presentation.api.health_routes import health
from presentation.api.webhook_routes import webhooks
from presentation.providers.admin import (
    get_authenticate_mini_app_uc,
    get_create_bot_uc,
    get_get_bot_uc,
    get_publish_bot_uc,
    get_save_flow_draft_uc,
)
from presentation.providers.system import get_healthcheck_uc, get_services_healthcheck_uc
from presentation.providers.webhooks import (
    get_idempotency,
    get_platform_factory,
    get_process_update_uc,
)

MSK = timezone(timedelta(hours=3))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.startup_time_service = datetime.now(tz=MSK)
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.engine.dispose()


def create_app() -> FastAPI:
    settings = Settings()
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    http_client = httpx.AsyncClient(timeout=10.0)

    bots = PgBotRepository(session_factory)
    flows = PgFlowRepository(session_factory)
    sessions = PgSessionRepository(session_factory)
    token_vault = FileTokenVault(settings.token_vault_file)
    platform_factory = RegistryPlatformFactory(
        {
            Platform.TELEGRAM: TelegramBotAdapter(http_client),
            Platform.MAX: MaxBotAdapter(http_client),
        }
    )
    idempotency = RedisIdempotency.from_settings(settings)

    app = FastAPI(
        title="meta-bot-core",
        description="Доменное ядро конструктора сценариев чат-ботов и mini app (Telegram, MAX)",
        version=get_app_version("meta-bot-core"),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.http_client = http_client

    app.include_router(health, prefix="/healthchecks", tags=["Состояние"])
    app.include_router(admin, prefix="/api", tags=["Конструктор"])
    app.include_router(webhooks, prefix="/webhooks", tags=["Вебхуки"])

    # DI провайдеров presentation — здесь, чтобы presentation не импортировал
    # infrastructure (контракт .importlinter).
    overrides = {
        get_healthcheck_uc: lambda: GetHealthcheckUseCase(project_name=settings.project_name, url=settings.public_url),
        get_services_healthcheck_uc: lambda: GetServicesHealthcheckUseCase(
            registry=SettingsHealthServiceRegistry(settings),
            probe=InfraHealthServiceProbe(settings),
        ),
        get_create_bot_uc: lambda: CreateBotUseCase(bots=bots, token_vault=token_vault),
        get_get_bot_uc: lambda: GetBotUseCase(bots=bots),
        get_save_flow_draft_uc: lambda: SaveFlowDraftUseCase(bots=bots, flows=flows),
        get_authenticate_mini_app_uc: lambda: AuthenticateMiniAppUseCase(
            bots=bots, token_vault=token_vault, platform_factory=platform_factory
        ),
        get_publish_bot_uc: lambda: PublishBotUseCase(
            bots=bots, flows=flows, token_vault=token_vault, platform_factory=platform_factory
        ),
        get_platform_factory: lambda: platform_factory,
        get_idempotency: lambda: idempotency,
        get_process_update_uc: lambda: ProcessUpdateUseCase(
            bots=bots,
            flows=flows,
            sessions=sessions,
            token_vault=token_vault,
            platform_factory=platform_factory,
        ),
    }
    app.dependency_overrides.update(overrides)
    return app


app = create_app()
