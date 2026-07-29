"""Composition root meta-bot-core.

Единственное место, где слои склеиваются: создание зависимостей, DI
(dependency_overrides провайдеров presentation), регистрация платформенных
адаптеров в PlatformFactory, маршруты FastAPI. Только здесь допустимы импорты
из всех слоёв сразу (memory-bank/architecture/overview.md).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI

from application.system.use_cases.get_healthcheck import GetHealthcheckUseCase, get_app_version
from application.system.use_cases.get_services_healthcheck import GetServicesHealthcheckUseCase
from application.use_cases.attach_mini_app import AttachMiniAppUseCase
from application.use_cases.authenticate_mini_app import AuthenticateMiniAppUseCase
from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.get_flow_draft import GetFlowDraftUseCase
from application.use_cases.list_bots import ListBotsUseCase
from application.use_cases.process_update import ProcessUpdateUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.purge_expired_sessions import PurgeExpiredSessionsUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from application.use_cases.set_connection_secret import SetConnectionSecretUseCase
from application.use_cases.set_events_token import SetEventsTokenUseCase
from application.use_cases.set_notification_target import SetNotificationTargetUseCase
from application.use_cases.submit_external_event import SubmitExternalEventUseCase
from application.use_cases.submit_mini_app_result import SubmitMiniAppResultUseCase
from domain.bot.value_objects import Platform
from infrastructure.cache.redis_idempotency import RedisIdempotency
from infrastructure.config import Settings
from infrastructure.db.engine import build_engine, build_session_factory
from infrastructure.db.repositories import PgBotRepository, PgFlowRepository, PgSessionRepository
from infrastructure.http.httpx_client import HttpxClient
from infrastructure.integrations.health_checks import (
    InfraHealthServiceProbe,
    SettingsHealthServiceRegistry,
)
from infrastructure.maintenance.session_purge import run_periodic_purge
from infrastructure.observability.logging_setup import configure_logging
from infrastructure.platforms.factory import RegistryPlatformFactory
from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.max.tls import build_max_http_client
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter
from infrastructure.security.file_connection_secrets import FileConnectionSecrets
from infrastructure.security.file_events_tokens import FileEventsTokens
from infrastructure.security.file_notification_targets import FileNotificationTargets
from infrastructure.security.file_token_vault import FileTokenVault
from presentation.api.admin_routes import admin
from presentation.api.health_routes import health
from presentation.api.webhook_routes import webhooks
from presentation.middleware.cors import add_cors_middleware
from presentation.middleware.request_context import request_context_middleware
from presentation.providers.admin import (
    get_attach_mini_app_uc,
    get_authenticate_mini_app_uc,
    get_create_bot_uc,
    get_get_bot_uc,
    get_get_flow_draft_uc,
    get_list_bots_uc,
    get_publish_bot_uc,
    get_save_flow_draft_uc,
    get_set_connection_secret_uc,
    get_set_events_token_uc,
    get_set_notification_target_uc,
    get_submit_external_event_uc,
    get_submit_mini_app_result_uc,
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
    purge_task = asyncio.create_task(
        run_periodic_purge(app.state.purge_sessions, app.state.settings.session_purge_interval)
    )
    try:
        yield
    finally:
        purge_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await purge_task
        await app.state.http_client.aclose()
        await app.state.max_http_client.aclose()
        await app.state.engine.dispose()


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level, settings.log_dir)  # ADR-0013: до любых логгеров
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    http_client = httpx.AsyncClient(timeout=10.0)
    # MAX-адаптер — отдельный клиент с суженным доверием к сертификату Минцифры
    # (только соединения с MAX доверяют этому корню, не весь трафик).
    max_http_client = build_max_http_client(ca_bundle=settings.max_ca_bundle, timeout=10.0)

    bots = PgBotRepository(session_factory)
    flows = PgFlowRepository(session_factory)
    sessions = PgSessionRepository(session_factory)
    token_vault = FileTokenVault(settings.token_vault_file)
    platform_factory = RegistryPlatformFactory(
        {
            Platform.TELEGRAM: TelegramBotAdapter(http_client),
            Platform.MAX: MaxBotAdapter(max_http_client),
        }
    )
    idempotency = RedisIdempotency.from_settings(settings)
    connection_secrets = FileConnectionSecrets(settings.connection_secrets_file)
    notification_targets = FileNotificationTargets(settings.notification_targets_file)
    events_tokens = FileEventsTokens(settings.events_tokens_file)
    process_update = ProcessUpdateUseCase(
        bots=bots,
        flows=flows,
        sessions=sessions,
        token_vault=token_vault,
        platform_factory=platform_factory,
        http_client=HttpxClient(http_client),
        secrets=connection_secrets,
        notifications=notification_targets,
    )

    app = FastAPI(
        title="meta-bot-core",
        description="Доменное ядро конструктора сценариев чат-ботов и mini app (Telegram, MAX)",
        version=get_app_version("meta-bot-core"),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.http_client = http_client
    app.state.max_http_client = max_http_client
    app.state.purge_sessions = PurgeExpiredSessionsUseCase(
        sessions,
        idle_ttl_seconds=settings.session_idle_ttl,
        retention_seconds=settings.session_retention_days * 86400,
    )

    app.middleware("http")(request_context_middleware)  # request_id + доступ-лог + единый 500
    # CORS для браузерного mini app с внешнего хостинга (ADR-0006): только
    # точные origin'ы из настроек (валидатор Settings запрещает wildcard);
    # пусто — middleware не подключается вовсе (dev, same-origin).
    add_cors_middleware(app, allowed_origins=settings.cors_allowed_origins)
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
        get_list_bots_uc: lambda: ListBotsUseCase(bots=bots),
        get_save_flow_draft_uc: lambda: SaveFlowDraftUseCase(bots=bots, flows=flows),
        get_get_flow_draft_uc: lambda: GetFlowDraftUseCase(bots=bots, flows=flows),
        get_authenticate_mini_app_uc: lambda: AuthenticateMiniAppUseCase(
            bots=bots, token_vault=token_vault, platform_factory=platform_factory
        ),
        get_attach_mini_app_uc: lambda: AttachMiniAppUseCase(bots=bots),
        get_set_connection_secret_uc: lambda: SetConnectionSecretUseCase(bots=bots, secrets=connection_secrets),
        get_set_notification_target_uc: lambda: SetNotificationTargetUseCase(bots=bots, targets=notification_targets),
        get_set_events_token_uc: lambda: SetEventsTokenUseCase(bots=bots, tokens=events_tokens),
        get_submit_external_event_uc: lambda: SubmitExternalEventUseCase(
            bots=bots,
            events_tokens=events_tokens,
            targets=notification_targets,
            idempotency=idempotency,
            process_update=process_update,
            # Продление аренды ключа заметно чаще её срока — иначе ключ истечёт
            # под живым исполнением (ADR-0019, ops/configuration.md).
            lease_heartbeat_seconds=settings.events_inflight_ttl / 3,
        ),
        get_submit_mini_app_result_uc: lambda: SubmitMiniAppResultUseCase(
            bots=bots,
            token_vault=token_vault,
            platform_factory=platform_factory,
            process_update=process_update,
        ),
        get_publish_bot_uc: lambda: PublishBotUseCase(
            bots=bots,
            flows=flows,
            token_vault=token_vault,
            platform_factory=platform_factory,
            # Форму пути вебхука знает composition root — он же монтирует роут
            # /webhooks/{platform}/{bot_id} выше (ADR-0014).
            webhook_url_template=(
                settings.webhook_base_url.rstrip("/") + "/webhooks/{platform}/{bot_id}"
                if settings.webhook_base_url
                else None
            ),
            webhook_secret=settings.webhook_secret,
        ),
        get_platform_factory: lambda: platform_factory,
        get_idempotency: lambda: idempotency,
        get_process_update_uc: lambda: process_update,
    }
    app.dependency_overrides.update(overrides)
    return app


app = create_app()
