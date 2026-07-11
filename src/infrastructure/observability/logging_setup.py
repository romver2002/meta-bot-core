"""Настройка структурного логирования (ADR-0013, спека ops/observability.md).

Каждая запись — одна JSON-строка: ts, level, logger, message, request_id,
доп. поля из ``extra``. Всегда stdout (12-factor); при заданном LOG_DIR —
дополнительно ротируемые файлы ``app.log`` (всё) и ``errors.log`` (ERROR+),
локально смонтированные на хост (docker-compose ./logs).

Секреты и ПДн в логи не попадают по правилам спеки: тексты пользователей —
только на DEBUG, токены — никогда (за скрабом следят адаптеры).
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from application.observability import current_request_id

# Скраб токена бота в ЛЮБОЙ записи (защита в глубину): httpx и другие библиотеки
# пишут полные URL, а у Telegram токен живёт в пути (/bot<token>/метод).
_TOKEN_IN_PATH = re.compile(r"/bot[^/\s\"']+/")

# Служебные атрибуты LogRecord — всё остальное считаем полями ``extra``.
_RESERVED = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Однострочный JSON; несериализуемые значения приводятся к str.

    Токен бота (`/bot<token>/`) вычищается из message/exc_info/stack — даже
    если болтливая библиотека или чужой код попытаются его напечатать.
    """

    #: Поля конверта записи — extra с такими же именами не может их перезаписать.
    _ENVELOPE = frozenset({"ts", "level", "logger", "message", "request_id", "exc_info", "stack"})

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": _TOKEN_IN_PATH.sub("/bot***/", record.getMessage()),
        }
        request_id = current_request_id()
        if request_id is not None:
            entry["request_id"] = request_id
        entry.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _RESERVED and key not in self._ENVELOPE and not key.startswith("_")
            }
        )
        if record.exc_info:
            entry["exc_info"] = _TOKEN_IN_PATH.sub("/bot***/", self.formatException(record.exc_info))
        if record.stack_info:
            entry["stack"] = _TOKEN_IN_PATH.sub("/bot***/", self.formatStack(record.stack_info))
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", log_dir: str | None = None) -> None:
    """Настраивает root-логгер: stdout всегда, файлы — только при log_dir."""
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = []

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    handlers.append(stdout_handler)

    if log_dir:
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        app_file = logging.handlers.RotatingFileHandler(
            directory / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        app_file.setFormatter(formatter)
        handlers.append(app_file)
        errors_file = logging.handlers.RotatingFileHandler(
            directory / "errors.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        errors_file.setFormatter(formatter)
        errors_file.setLevel(logging.ERROR)
        handlers.append(errors_file)

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers = handlers

    # Болтливые сторонние логгеры: httpx пишет на INFO полный URL каждого
    # запроса — у Telegram в URL токен. Поднимаем их порог независимо от LOG_LEVEL.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
