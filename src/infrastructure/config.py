"""Настройки инфраструктуры (pydantic-settings).

Значения приходят из переменных окружения / .env (compose передаёт
DATABASE_URL и REDIS_URL). Дефолты соответствуют локальному compose.
Секреты (токены ботов) сюда не попадают — они живут в token vault.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация подключения и TTL (ops/configuration.md, ADR-0008)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_name: str = "meta-bot-core"
    public_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://metabot:metabot@localhost:5433/metabot"
    redis_url: str = "redis://localhost:6379/0"
    session_idle_ttl: int = 3600
    webhook_idempotency_ttl: int = 86400
    webhook_secret: str | None = None  # сверяется с X-*-Secret заголовком платформы
    # Путь к файлу dev-vault (не секрет); прод-хранилище — открытый вопрос.
    token_vault_file: str = ".secrets/token-vault.json"  # noqa: S105
