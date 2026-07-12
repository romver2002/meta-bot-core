"""answer_callback адаптеров: точный HTTP-контракт платформ (MockTransport).

TG: POST /bot{token}/answerCallbackQuery, id в ТЕЛЕ (callback_query_id).
MAX: POST /answers, id в QUERY (callback_id), токен в Authorization.
Контракты — specs/002-platform-deep-dive/report.md, «Ответ на нажатие».
"""

from __future__ import annotations

import json

import httpx
import pytest

from application.errors import ApplicationError
from application.ports.bot_platform import AnswerCallbackCommand
from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter

pytestmark = pytest.mark.unit


def _capturing_client(captured: list[httpx.Request], status_code: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status_code, json={"ok": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_telegram_answer_callback_contract() -> None:
    captured: list[httpx.Request] = []
    adapter = TelegramBotAdapter(_capturing_client(captured))

    await adapter.answer_callback(AnswerCallbackCommand(bot_token="12345:tok", callback_id="cbq-1"))

    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/bot12345:tok/answerCallbackQuery"
    assert request.read() == b'{"callback_query_id":"cbq-1"}'  # id в теле


async def test_max_answer_callback_contract() -> None:
    captured: list[httpx.Request] = []
    adapter = MaxBotAdapter(_capturing_client(captured))

    await adapter.answer_callback(AnswerCallbackCommand(bot_token="max-token", callback_id="cb-xyz"))

    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/answers"
    assert request.url.params["callback_id"] == "cb-xyz"  # id в query, не в теле
    assert request.headers["Authorization"] == "max-token"
    # MAX требует непустое тело: пустая notification гасит «часики» без тоста
    # (на {} MAX отвечает 400 message/notification required — проверено live 2026-07-12).
    assert json.loads(request.read()) == {"notification": ""}


async def test_http_error_becomes_application_error() -> None:
    captured: list[httpx.Request] = []
    telegram = TelegramBotAdapter(_capturing_client(captured, status_code=500))
    max_adapter = MaxBotAdapter(_capturing_client(captured, status_code=500))

    with pytest.raises(ApplicationError):
        await telegram.answer_callback(AnswerCallbackCommand(bot_token="t", callback_id="x"))
    with pytest.raises(ApplicationError):
        await max_adapter.answer_callback(AnswerCallbackCommand(bot_token="t", callback_id="x"))


async def test_telegram_error_chain_does_not_leak_token() -> None:
    # 400 «query is too old» — типовой ответ на протухший callback_id; текст
    # httpx-ошибки содержит URL с /bot<token>/ — в ApplicationError и её
    # цепочке __cause__ токена быть не должно (architecture/security.md).
    adapter = TelegramBotAdapter(_capturing_client([], status_code=400))
    secret_token = "987654:SECRET-abc"

    with pytest.raises(ApplicationError) as excinfo:
        await adapter.answer_callback(AnswerCallbackCommand(bot_token=secret_token, callback_id="x"))

    chain_text = repr(excinfo.value) + repr(excinfo.value.__cause__) + repr(excinfo.value.__context__)
    assert secret_token not in chain_text
    assert "/bot***/" in str(excinfo.value)  # URL сохранён для диагностики, токен вычищен
