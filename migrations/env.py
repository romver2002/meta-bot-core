"""Alembic env: async-движок, URL — из Settings (env DATABASE_URL приоритетнее .env)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from infrastructure.config import Settings
from infrastructure.db.models import Base

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False обязателен: по умолчанию fileConfig глушит
    # ВСЕ уже созданные логгеры, которых нет в alembic.ini, — то есть все наши
    # app.*. Когда миграции гонятся в одном процессе с приложением (фикстура
    # интеграционных тестов, разовый прогон из кода), после апгрейда приложение
    # молча перестаёт логировать. Alembic'у нужны свои логгеры, а не тишина
    # у чужих.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    return Settings().database_url


def run_migrations_offline() -> None:
    """Генерация SQL без подключения к БД (alembic upgrade --sql)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
