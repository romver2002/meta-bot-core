"""Настройки инфраструктуры (pydantic-settings).

Значения приходят из переменных окружения / .env (compose передаёт
DATABASE_URL и REDIS_URL). Дефолты соответствуют локальному compose.
Секреты (токены ботов) сюда не попадают — они живут в token vault.
"""

from __future__ import annotations

import contextlib
import re
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_TCP_PORT = 65_535
_DEFAULT_PORTS = {"http": 80, "https": 443}
# Пересечение алфавитов секрета вебхука обеих платформ (specs/002, «Установка
# webhook»): Telegram secret_token — [A-Za-z0-9_-] 1..256, MAX secret —
# [A-Za-z0-9-] 5..256. Общий безопасный набор: [A-Za-z0-9-], длина 5..256.
_WEBHOOK_SECRET_RE = re.compile(r"^[A-Za-z0-9-]{5,256}$")


def _canonical_origin(origin: str) -> str:
    """Приводит origin к форме, в которой его шлёт браузер (Origin-заголовок).

    Браузер отдаёт scheme/host в нижнем регистре, IDN — в punycode, дефолтный
    порт (80/443) опускает. Starlette сравнивает origin строго и регистрозависимо,
    поэтому неканоничная запись в конфиге молча никогда не совпала бы.
    """
    parsed = urlsplit(origin)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").rstrip(".")
    with contextlib.suppress(UnicodeError):
        host = host.encode("idna").decode("ascii")
    port = parsed.port
    if port is None or port == _DEFAULT_PORTS.get(scheme):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


class Settings(BaseSettings):
    """Конфигурация подключения и TTL (ops/configuration.md, ADR-0008)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_name: str = "meta-bot-core"
    public_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://metabot:metabot@localhost:5433/metabot"
    redis_url: str = "redis://localhost:6379/0"
    session_idle_ttl: int = 3600
    # Ретеншен ПДн сессий (BR-008, ADR-0011): срок хранения завершённых/просроченных
    # сессий и интервал фоновой чистки (секунды).
    session_retention_days: int = 30
    session_purge_interval: int = 3600
    webhook_idempotency_ttl: int = 86400
    webhook_secret: str | None = None  # сверяется с X-*-Secret заголовком платформы
    # Публичный HTTPS-адрес приёма вебхуков (ADR-0014): при заданном значении
    # publish сам регистрирует /webhooks/{platform}/{bot_id} у платформы;
    # пусто — регистрация остаётся ручной (dev без туннеля).
    webhook_base_url: str | None = None
    # Точные origin'ы web-клиентов (JSON-массив в env); пусто — CORS выключен.
    cors_allowed_origins: tuple[str, ...] = ()
    # Логирование (ADR-0013): уровень и опциональный каталог файлов app.log/errors.log
    # (локальная разработка; в проде LOG_DIR не задаётся — только stdout).
    log_level: str = "INFO"
    log_dir: str | None = None
    # Пути к dev-хранилищам секретов (сами пути — не секрет; прод — открытый вопрос).
    token_vault_file: str = ".secrets/token-vault.json"  # noqa: S105 — путь к файлу, не пароль
    connection_secrets_file: str = ".secrets/connections.json"
    notification_targets_file: str = ".secrets/notification-targets.json"
    # Доп. корневой CA для доверия ТОЛЬКО в MAX-адаптере (сертификат Минцифры):
    # platform-api2.max.ru отдаёт цепочку под этот корень, которого нет в certifi.
    # Пусто/файла нет — MAX-клиент на дефолтном доверии (TLS к MAX упадёт).
    max_ca_bundle: str = "ops/certs/russian_trusted_root_ca.pem"

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        """Принимает только точные HTTP(S) origin без wildcard, path и credentials."""
        for origin in origins:
            parsed = urlsplit(origin)
            try:
                port = parsed.port
            except ValueError as exc:
                raise ValueError(f"Некорректный CORS origin: {origin!r}") from exc

            is_exact_origin = (
                origin == origin.strip()
                and "*" not in origin
                and parsed.scheme in {"http", "https"}
                and parsed.hostname is not None
                and parsed.username is None
                and parsed.password is None
                and parsed.path == ""
                and parsed.query == ""
                and parsed.fragment == ""
                and (port is None or 0 < port <= MAX_TCP_PORT)
            )
            if not is_exact_origin:
                raise ValueError(f"CORS origin должен быть точным http(s) origin без path и wildcard: {origin!r}")
        # Канонизируем под форму браузера — иначе валидный на вид origin
        # (верхний регистр, IDN-Unicode, явный дефолтный порт) не совпал бы.
        return tuple(_canonical_origin(origin) for origin in origins)

    @field_validator("webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, secret: str | None) -> str | None:
        """С ADR-0014 секрет уходит платформам при publish — проверяем алфавит/длину.

        Секрет с недопустимым символом (например ``_`` для MAX) или короче 5
        символов навсегда провалил бы регистрацию вебхука 502-ошибкой, а причину
        пришлось бы выуживать из ответа платформы. Пустая строка из env
        (``WEBHOOK_SECRET=`` / compose ``${WEBHOOK_SECRET:-}``) = «не задано» -> None.
        """
        if secret is None or not secret.strip():
            return None
        if not _WEBHOOK_SECRET_RE.match(secret):
            raise ValueError(
                "WEBHOOK_SECRET: допустимы 5..256 символов [A-Za-z0-9-] "
                "(пересечение требований Telegram и MAX, specs/002)"
            )
        return secret
