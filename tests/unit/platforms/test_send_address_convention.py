"""Конвенция адреса ``user:<id>`` в send_message (ADR-0017, push-доставка).

MAX: chat_id диалога уникален для пары «пользователь ↔ бот» и снаружи
неизвестен — push идёт по глобальному user_id (``?user_id=``). Telegram:
в личке chat_id == user_id — префикс просто снимается. Обычные адреса
из входящих update шлются как раньше (chat_id).
"""

from __future__ import annotations

import json

import httpx
import pytest

from application.ports.bot_platform import SendMessageCommand
from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter

pytestmark = pytest.mark.unit


def _client(captured: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# Синтетические идентификаторы: реальные ID получателей живут только
# в `.secrets/` и в репозитории потребителя, в git их быть не должно.
USER_ID = "100000001"
CHAT_ID = "200000002"


def _command(address: str) -> SendMessageCommand:
    return SendMessageCommand(bot_token="tok", external_chat_id=address, text="Уведомление", buttons=())


async def test_max_user_prefix_becomes_user_id_param() -> None:
    captured: list[httpx.Request] = []
    await MaxBotAdapter(_client(captured)).send_message(_command(f"user:{USER_ID}"))

    assert captured[0].url.params["user_id"] == USER_ID
    assert "chat_id" not in captured[0].url.params


async def test_max_plain_address_stays_chat_id() -> None:
    captured: list[httpx.Request] = []
    await MaxBotAdapter(_client(captured)).send_message(_command(CHAT_ID))

    assert captured[0].url.params["chat_id"] == CHAT_ID
    assert "user_id" not in captured[0].url.params


async def test_telegram_user_prefix_is_stripped() -> None:
    captured: list[httpx.Request] = []
    await TelegramBotAdapter(_client(captured)).send_message(_command(f"user:{USER_ID}"))

    assert json.loads(captured[0].content)["chat_id"] == USER_ID


async def test_telegram_plain_address_unchanged() -> None:
    captured: list[httpx.Request] = []
    await TelegramBotAdapter(_client(captured)).send_message(_command("777"))

    assert json.loads(captured[0].content)["chat_id"] == "777"
