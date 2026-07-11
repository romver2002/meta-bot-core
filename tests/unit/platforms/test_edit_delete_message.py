"""edit_message/delete_message адаптеров: точный HTTP-контракт платформ (ADR-0012).

TG: POST /bot{token}/editMessageText | /deleteMessage, адресация chat_id +
message_id (Integer) в ТЕЛЕ; «message is not modified» — успех, не сбой.
MAX: PUT | DELETE /messages, message_id (string) в QUERY, токен в Authorization;
attachments: [] снимает клавиатуру (null означал бы «не менять» — не наш случай).
Контракты — specs/002-platform-deep-dive/report.md, «Messaging / форматирование».
"""

from __future__ import annotations

import json

import httpx
import pytest

from application.errors import ApplicationError
from application.ports.bot_platform import DeleteMessageCommand, EditMessageCommand
from domain.flow.entities import Button
from domain.flow.value_objects import ButtonAction
from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter

pytestmark = pytest.mark.unit

BUTTONS = (Button(label="Дальше", action=ButtonAction.NEXT, target="finish"),)


def _client(
    captured: list[httpx.Request],
    status_code: int = 200,
    body: dict[str, object] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status_code, json=body if body is not None else {"ok": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _edit(message_id: str = "314", buttons: tuple[Button, ...] = ()) -> EditMessageCommand:
    return EditMessageCommand(
        bot_token="12345:tok",
        external_chat_id="4242",
        message_id=message_id,
        text="Готово",
        buttons=buttons,
    )


def _delete(message_id: str = "314") -> DeleteMessageCommand:
    return DeleteMessageCommand(bot_token="12345:tok", external_chat_id="4242", message_id=message_id)


# ── Telegram ─────────────────────────────────────────────────────────────────


async def test_telegram_edit_contract_with_keyboard() -> None:
    captured: list[httpx.Request] = []
    adapter = TelegramBotAdapter(_client(captured))

    await adapter.edit_message(_edit(buttons=BUTTONS))

    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/bot12345:tok/editMessageText"
    body = json.loads(request.read())
    assert body["chat_id"] == "4242"
    assert body["message_id"] == 314  # нейтральный str -> Integer только внутри TG-адаптера
    assert body["text"] == "Готово"
    assert body["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "finish"


async def test_telegram_edit_without_buttons_removes_keyboard() -> None:
    captured: list[httpx.Request] = []
    adapter = TelegramBotAdapter(_client(captured))

    await adapter.edit_message(_edit())

    body = json.loads(captured[0].read())
    # reply_markup не передаётся — Telegram снимает inline-клавиатуру:
    # протухшее меню не остаётся кликабельным (семантика EditMessageCommand).
    assert "reply_markup" not in body


async def test_telegram_edit_not_modified_is_success() -> None:
    # Правка в идентичное содержимое: без этой обработки движок отправил бы
    # дублирующее новое сообщение по фолбэку.
    adapter = TelegramBotAdapter(
        _client([], status_code=400, body={"ok": False, "description": "Bad Request: message is not modified"})
    )

    await adapter.edit_message(_edit())  # не бросает


async def test_telegram_edit_rejection_raises_and_scrubs_token() -> None:
    adapter = TelegramBotAdapter(
        _client([], status_code=400, body={"ok": False, "description": "Bad Request: message to edit not found"})
    )

    with pytest.raises(ApplicationError) as excinfo:
        await adapter.edit_message(_edit())

    chain_text = repr(excinfo.value) + repr(excinfo.value.__cause__) + repr(excinfo.value.__context__)
    assert "12345:tok" not in chain_text
    assert "/bot***/" in str(excinfo.value)


async def test_telegram_delete_contract() -> None:
    captured: list[httpx.Request] = []
    adapter = TelegramBotAdapter(_client(captured))

    await adapter.delete_message(_delete())

    request = captured[0]
    assert request.url.path == "/bot12345:tok/deleteMessage"
    assert json.loads(request.read()) == {"chat_id": "4242", "message_id": 314}


async def test_telegram_delete_rejection_raises_and_scrubs_token() -> None:
    adapter = TelegramBotAdapter(_client([], status_code=400, body={"ok": False}))

    with pytest.raises(ApplicationError) as excinfo:
        await adapter.delete_message(_delete())

    assert "12345:tok" not in repr(excinfo.value) + repr(excinfo.value.__cause__)


async def test_telegram_non_numeric_message_id_is_application_error() -> None:
    # message_id нейтрально строковый (MAX), но у Telegram обязан быть числом;
    # мусор на входе — ошибка приложения, а не ValueError из глубины httpx.
    adapter = TelegramBotAdapter(_client([]))

    with pytest.raises(ApplicationError, match="message_id"):
        await adapter.edit_message(_edit(message_id="mid-abc"))
    with pytest.raises(ApplicationError, match="message_id"):
        await adapter.delete_message(_delete(message_id="mid-abc"))


# ── MAX ──────────────────────────────────────────────────────────────────────


async def test_max_edit_contract_with_keyboard() -> None:
    captured: list[httpx.Request] = []
    adapter = MaxBotAdapter(_client(captured, body={"success": True}))

    await adapter.edit_message(_edit(message_id="mid-menu", buttons=BUTTONS))

    request = captured[0]
    assert request.method == "PUT"
    assert request.url.path == "/messages"
    assert request.url.params["message_id"] == "mid-menu"  # id в query, не в теле
    assert request.headers["Authorization"] == "12345:tok"
    body = json.loads(request.read())
    assert body["text"] == "Готово"
    assert body["attachments"][0]["type"] == "inline_keyboard"


async def test_max_edit_without_buttons_sends_empty_attachments() -> None:
    captured: list[httpx.Request] = []
    adapter = MaxBotAdapter(_client(captured, body={"success": True}))

    await adapter.edit_message(_edit(message_id="mid-menu"))

    body = json.loads(captured[0].read())
    # [] = «удалить все вложения»; null означал бы «не менять» и оставил бы
    # протухшую клавиатуру кликабельной (specs/002, «Вложения при edit»).
    assert body["attachments"] == []


async def test_max_edit_success_false_raises() -> None:
    # У MAX PUT/DELETE поле message — СТРОКА ошибки при success=false,
    # HTTP-статус при этом может быть 200 (specs/002, «Форма ответа»).
    adapter = MaxBotAdapter(_client([], body={"success": False, "message": "message not found"}))

    with pytest.raises(ApplicationError, match="message not found"):
        await adapter.edit_message(_edit(message_id="mid-x"))


async def test_max_delete_contract() -> None:
    captured: list[httpx.Request] = []
    adapter = MaxBotAdapter(_client(captured, body={"success": True}))

    await adapter.delete_message(_delete(message_id="mid-menu"))

    request = captured[0]
    assert request.method == "DELETE"
    assert request.url.path == "/messages"
    assert request.url.params["message_id"] == "mid-menu"
    assert request.headers["Authorization"] == "12345:tok"


async def test_max_http_error_becomes_application_error() -> None:
    adapter = MaxBotAdapter(_client([], status_code=500, body={}))

    with pytest.raises(ApplicationError):
        await adapter.edit_message(_edit(message_id="mid-x"))
    with pytest.raises(ApplicationError):
        await adapter.delete_message(_delete(message_id="mid-x"))
