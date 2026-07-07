"""Health-check адаптеры вспомогательных сервисов: Postgres и Redis.

Паттерн sro-agent-core (registry + probe); у нас зависимые сервисы — не HTTP,
а инфраструктура из compose. Учётные данные из DSN в ответы не попадают.
"""

from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlsplit

import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from application.ports.health import HealthServiceProbeResult, HealthServiceTarget
from infrastructure.config import Settings


def _safe_location(dsn: str) -> str:
    """host:port из DSN — без схемы, пользователя и пароля."""
    parts = urlsplit(dsn)
    host = parts.hostname or "?"
    return f"{host}:{parts.port}" if parts.port else host


class SettingsHealthServiceRegistry:
    """Цели проверок из Settings: Postgres (хранилище) и Redis (FSM/идемпотентность)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_targets(self) -> list[HealthServiceTarget]:
        return [
            HealthServiceTarget(name="postgres", kind="postgres", domain=_safe_location(self._settings.database_url)),
            HealthServiceTarget(name="redis", kind="redis", domain=_safe_location(self._settings.redis_url)),
        ]


class InfraHealthServiceProbe:
    """Опрашивает инфраструктурную цель по её виду (postgres | redis)."""

    def __init__(self, settings: Settings, *, timeout: float = 5.0) -> None:
        self._settings = settings
        self._timeout = timeout

    async def check(self, target: HealthServiceTarget) -> HealthServiceProbeResult | None:
        try:
            if target.kind == "postgres":
                await self._check_postgres()
            elif target.kind == "redis":
                await self._check_redis()
            else:
                return None
        except Exception as exc:  # noqa: BLE001 - health endpoint reports per-service errors
            return HealthServiceProbeResult(
                service=target.name,
                url=target.domain,
                status_code=None,
                error=str(exc),
                status=HTTPStatus.BAD_REQUEST,
                info=None,
            )
        return HealthServiceProbeResult(
            service=target.name,
            url=target.domain,
            status_code=HTTPStatus.OK,
            status=HTTPStatus.OK,
            info={},
        )

    async def _check_postgres(self) -> None:
        engine = create_async_engine(
            self._settings.database_url,
            poolclass=NullPool,
            connect_args={"timeout": self._timeout},
        )
        try:
            async with engine.connect() as connection:
                await connection.execute(sa.text("SELECT 1"))
        finally:
            await engine.dispose()

    async def _check_redis(self) -> None:
        client: Redis = Redis.from_url(
            self._settings.redis_url,
            socket_connect_timeout=self._timeout,
            socket_timeout=self._timeout,
        )
        try:
            await client.ping()
        finally:
            await client.aclose()
