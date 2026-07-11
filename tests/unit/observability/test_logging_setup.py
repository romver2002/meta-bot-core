"""Структурное логирование (ADR-0013): JSON-формат, request_id, файлы ошибок."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from application.observability import bind_request_id, request_id_var
from infrastructure.observability.logging_setup import JsonFormatter, configure_logging

pytestmark = pytest.mark.unit


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_emits_single_line_json_with_extra() -> None:
    token = request_id_var.set(None)
    try:
        bind_request_id("req-123")
        line = JsonFormatter().format(_record("Update обработан", platform="telegram", bot_id="b1"))
    finally:
        request_id_var.reset(token)

    entry = json.loads(line)
    assert "\n" not in line  # одна строка — дружелюбно агрегаторам
    assert entry["level"] == "INFO"
    assert entry["logger"] == "app.test"
    assert entry["message"] == "Update обработан"
    assert entry["request_id"] == "req-123"
    assert (entry["platform"], entry["bot_id"]) == ("telegram", "b1")  # extra-поля попали
    assert entry["ts"].endswith("+00:00")  # UTC ISO-8601


def _boom() -> None:
    raise ValueError("boom")


def test_formatter_serializes_exception_and_unserializable_extra() -> None:
    record = _record("Ошибка", weird=object())
    try:
        _boom()
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()

    entry = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in entry["exc_info"]
    assert isinstance(entry["weird"], str)  # default=str — формат не падает


def test_bind_request_id_generates_when_empty_or_garbage() -> None:
    token = request_id_var.set(None)
    try:
        rid = bind_request_id(None)
        assert rid  # сгенерирован
        assert bind_request_id("  ")  # пробелы = пусто -> тоже генерирует
        assert bind_request_id("client-id") == "client-id"  # валидный входящий сохраняется
        # Недоверенный заголовок: мусор/управляющие/переросток не попадают в логи.
        assert bind_request_id("э\nвил") != "э\nвил"
        assert bind_request_id("x" * 200) != "x" * 200
    finally:
        request_id_var.reset(token)


def test_formatter_scrubs_bot_token_from_message_and_exc() -> None:
    # httpx на INFO печатает полный URL — у Telegram токен в пути. Защита в глубину:
    # форматтер вычищает /bot<token>/ из любой записи.
    record = _record("HTTP Request: GET https://api.telegram.org/bot123:SECRET-XYZ/getMe 200")
    line = JsonFormatter().format(record)
    assert "SECRET-XYZ" not in line
    assert "/bot***/" in line


def test_configure_logging_silences_noisy_http_loggers() -> None:
    configure_logging("DEBUG", None)
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_extra_cannot_overwrite_envelope_and_stack_info_serialized() -> None:
    record = _record("сообщение", level="FAKE", request_id="fake", ts="fake")
    record.stack_info = "Stack (most recent call last):\n  file x"
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "INFO"  # конверт не перезаписан extra-ключами
    assert entry.get("request_id") != "fake"
    assert entry["ts"] != "fake"
    assert "file x" in entry["stack"]  # stack_info не теряется


def test_configure_logging_writes_errors_file_only_for_errors(tmp_path: Path) -> None:
    configure_logging("INFO", str(tmp_path))
    try:
        logging.getLogger("app.test").warning("просто предупреждение")
        logging.getLogger("app.test").error("настоящая ошибка")
        for handler in logging.getLogger().handlers:
            handler.flush()

        app_lines = (tmp_path / "app.log").read_text(encoding="utf-8").splitlines()
        error_lines = (tmp_path / "errors.log").read_text(encoding="utf-8").splitlines()
    finally:
        configure_logging("INFO", None)  # не оставляем файловые хендлеры на tmp_path

    assert len(app_lines) == 2  # app.log получает всё
    assert len(error_lines) == 1  # errors.log — только ERROR (файл «где смотреть ошибки»)
    assert json.loads(error_lines[0])["message"] == "настоящая ошибка"
