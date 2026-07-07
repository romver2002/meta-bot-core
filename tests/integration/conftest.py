"""Интеграционный контур: реальный Postgres 16 через testcontainers.

Без запущенного Docker тесты честно скипаются (testing-strategy.md).
Миграции применяются Alembic'ом — тем самым проверяется и сама миграция.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ALL_TABLES = (
    "publish_audit",
    '"session"',
    "custom_code_versions",
    "mini_app",
    "bot",
    "flow_versions",
    "flow",
    "capability_matrix",
)


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16-alpine", driver="asyncpg")
        container.start()
    except Exception as exc:  # noqa: BLE001 — любой сбой Docker = окружение недоступно
        pytest.skip(f"Docker/testcontainers недоступны: {exc}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_pg_url(pg_url: str) -> str:
    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL"] = pg_url
    command.upgrade(Config("alembic.ini"), "head")
    return pg_url


@pytest.fixture
async def session_factory(migrated_pg_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_pg_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE"))
        await engine.dispose()
