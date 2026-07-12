"""register_webhook адаптеров: точный HTTP-контракт платформ (ADR-0014).

TG: POST /bot{token}/setWebhook, {url, secret_token} в ТЕЛЕ; ok=false — отказ,
токен в текст ошибки не попадает (скраб как у остальных методов).
MAX: POST /subscriptions, токен в Authorization, {url, secret} в теле; ответ
SimpleQueryResult — success=false означает отказ даже при HTTP 200.
Контракты — specs/002-platform-deep-dive/report.md, «Установка webhook».
"""

from __future__ import annotations

import json

import httpx
import pytest

from application.errors import ApplicationError
from application.ports.bot_platform import RegisterWebhookCommand
from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter

pytestmark = pytest.mark.unit

COMMAND = RegisterWebhookCommand(
    bot_token="12345:tok",
    url="https://bots.example/webhooks/telegram/bot-1",
    secret="wh-s3cret",
)


def _client(
    captured: list[httpx.Request],
    status_code: int = 200,
    body: dict[str, object] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status_code, json=body if body is not None else {"ok": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── Telegram ─────────────────────────────────────────────────────────────────


async def test_telegram_register_webhook_contract() -> None:
    captured: list[httpx.Request] = []
    adapter = TelegramBotAdapter(_client(captured))

    await adapter.register_webhook(COMMAND)

    (request,) = captured
    assert request.url.path == "/bot12345:tok/setWebhook"
    assert json.loads(request.content) == {
        "url": "https://bots.example/webhooks/telegram/bot-1",
        "secret_token": "wh-s3cret",
    }


async def test_telegram_register_webhook_without_secret_omits_field() -> None:
    captured: list[httpx.Request] = []
    adapter = TelegramBotAdapter(_client(captured))

    await adapter.register_webhook(RegisterWebhookCommand(bot_token="12345:tok", url="https://h/x"))

    assert json.loads(captured[0].content) == {"url": "https://h/x"}


async def test_telegram_register_webhook_ok_false_is_error() -> None:
    adapter = TelegramBotAdapter(_client([], body={"ok": False, "description": "bad webhook: HTTPS url required"}))

    with pytest.raises(ApplicationError, match="HTTPS url required"):
        await adapter.register_webhook(COMMAND)


async def test_telegram_register_webhook_error_scrubs_token() -> None:
    adapter = TelegramBotAdapter(_client([], status_code=500, body={}))

    with pytest.raises(ApplicationError) as excinfo:
        await adapter.register_webhook(COMMAND)
    assert "12345:tok" not in str(excinfo.value)  # токен вычищен из URL httpx-ошибки


async def test_telegram_register_webhook_non_json_200_is_application_error() -> None:
    # 2xx с не-JSON телом (страница туннеля/прокси): контракт порта — только
    # ApplicationError, сырой JSONDecodeError наружу выпускать нельзя.
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>ngrok tunnel offline</html>")

    adapter = TelegramBotAdapter(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(ApplicationError, match="не-JSON"):
        await adapter.register_webhook(COMMAND)


async def test_telegram_register_webhook_json_non_object_is_application_error() -> None:
    # ok=false-ветка не должна падать AttributeError на JSON-не-объекте ([]).
    adapter = TelegramBotAdapter(_client([], body=[]))  # type: ignore[arg-type]

    with pytest.raises(ApplicationError, match="отклонён"):
        await adapter.register_webhook(COMMAND)


# ── MAX ──────────────────────────────────────────────────────────────────────


async def test_max_register_webhook_contract() -> None:
    captured: list[httpx.Request] = []
    adapter = MaxBotAdapter(_client(captured, body={"success": True}))

    await adapter.register_webhook(COMMAND)

    (request,) = captured
    assert request.url.path == "/subscriptions"
    assert request.method == "POST"
    assert request.headers["Authorization"] == "12345:tok"
    assert json.loads(request.content) == {
        "url": "https://bots.example/webhooks/telegram/bot-1",
        "secret": "wh-s3cret",
    }


async def test_max_register_webhook_success_false_is_error() -> None:
    adapter = MaxBotAdapter(_client([], body={"success": False, "message": "invalid url"}))

    with pytest.raises(ApplicationError, match="invalid url"):
        await adapter.register_webhook(COMMAND)
