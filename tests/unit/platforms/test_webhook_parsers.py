"""Парсеры update платформ -> IncomingEvent (чистые функции адаптеров)."""

import pytest

from domain.bot.value_objects import Platform
from domain.flow.value_objects import TriggerType
from infrastructure.platforms.max.webhook import parse_max_update
from infrastructure.platforms.telegram.webhook import parse_telegram_update

pytestmark = pytest.mark.unit

BOT = "bot-1"


def test_telegram_text_message() -> None:
    event = parse_telegram_update(
        BOT,
        {"update_id": 7, "message": {"text": "привет", "from": {"id": 42}, "chat": {"id": 4242}}},
    )
    assert event is not None
    assert (event.platform, event.event_type) == (Platform.TELEGRAM, TriggerType.TEXT)
    assert (event.external_user_id, event.external_chat_id) == ("42", "4242")
    assert event.text == "привет"
    assert event.update_id == "7"
    assert event.callback_id is None  # текст — не нажатие: подтверждать нечего


def test_telegram_start_command() -> None:
    event = parse_telegram_update(
        BOT, {"update_id": 8, "message": {"text": "/start", "from": {"id": 42}, "chat": {"id": 42}}}
    )
    assert event is not None
    assert event.event_type is TriggerType.START


def test_telegram_callback() -> None:
    event = parse_telegram_update(
        BOT,
        {
            "update_id": 9,
            "callback_query": {
                "id": "cbq-1",
                "from": {"id": 42},
                "data": "finish",
                "message": {"chat": {"id": 4242}},
            },
        },
    )
    assert event is not None
    assert event.event_type is TriggerType.CALLBACK
    assert event.payload == "finish"
    assert event.external_chat_id == "4242"
    assert event.callback_id == "cbq-1"  # для answerCallbackQuery (гасит спиннер)


def test_telegram_unsupported_update_ignored() -> None:
    assert parse_telegram_update(BOT, {"update_id": 10, "edited_message": {}}) is None


def test_max_bot_started() -> None:
    event = parse_max_update(
        BOT, {"update_type": "bot_started", "timestamp": 1000, "user": {"user_id": 5}, "chat_id": 55}
    )
    assert event is not None
    assert (event.platform, event.event_type) == (Platform.MAX, TriggerType.START)
    assert (event.external_user_id, event.external_chat_id) == ("5", "55")
    # Нет per-update id → составной ключ идемпотентности.
    assert event.update_id == "bot_started:1000:5"


def test_max_message_uses_mid_as_idempotency_key() -> None:
    payload = {
        "update_type": "message_created",
        "timestamp": 2000,
        "message": {
            "sender": {"user_id": 5},
            "recipient": {"chat_id": 55},
            "body": {"mid": "mid-abc", "text": "меню"},
        },
    }
    event = parse_max_update(BOT, payload)
    assert event is not None
    assert event.event_type is TriggerType.TEXT
    assert event.text == "меню"
    assert event.update_id == "mid-abc"  # стабилен между ретраями доставки
    assert event.callback_id is None  # текст — не нажатие: подтверждать нечего

    payload["message"]["body"]["text"] = "/start"  # type: ignore[index]
    started = parse_max_update(BOT, payload)
    assert started is not None
    assert started.event_type is TriggerType.START


def test_max_message_without_mid_falls_back_to_composite() -> None:
    event = parse_max_update(
        BOT,
        {
            "update_type": "message_created",
            "timestamp": 2001,
            "message": {"sender": {"user_id": 7}, "recipient": {"chat_id": 70}, "body": {"text": "hi"}},
        },
    )
    assert event is not None
    assert event.update_id == "message_created:2001:7"


def test_max_callback_uses_callback_id() -> None:
    event = parse_max_update(
        BOT,
        {
            "update_type": "message_callback",
            "timestamp": 3000,
            "callback": {"callback_id": "cb-xyz", "payload": "finish", "user": {"user_id": 5}},
            "message": {"recipient": {"chat_id": 55}},
        },
    )
    assert event is not None
    assert event.event_type is TriggerType.CALLBACK
    assert event.payload == "finish"
    assert event.update_id == "cb-xyz"
    assert event.callback_id == "cb-xyz"  # для POST /answers (defensive-политика)


def test_max_unsupported_update_ignored() -> None:
    assert parse_max_update(BOT, {"update_type": "user_added", "timestamp": 1}) is None
