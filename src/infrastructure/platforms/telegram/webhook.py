"""Парсинг Telegram Update -> IncomingEvent (ADR-0004).

Формат — core.telegram.org/bots/api#update; наружу уходит только
платформонезависимый IncomingEvent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from domain.bot.value_objects import Platform
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType


def parse_telegram_update(bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
    update_id = str(payload["update_id"]) if "update_id" in payload else None

    message = cast("dict[str, Any] | None", payload.get("message"))
    if message is not None and "text" in message:
        text = str(message["text"])
        return IncomingEvent(
            platform=Platform.TELEGRAM,
            bot_id=bot_id,
            external_user_id=str(message["from"]["id"]),
            external_chat_id=str(message["chat"]["id"]),
            event_type=TriggerType.START if text.startswith("/start") else TriggerType.TEXT,
            text=text,
            update_id=update_id,
        )

    callback = cast("dict[str, Any] | None", payload.get("callback_query"))
    if callback is not None:
        origin = cast("dict[str, Any]", callback.get("message") or {})
        chat = cast("dict[str, Any]", origin.get("chat") or {})
        callback_id = callback.get("id")
        return IncomingEvent(
            platform=Platform.TELEGRAM,
            bot_id=bot_id,
            external_user_id=str(callback["from"]["id"]),
            external_chat_id=str(chat.get("id", callback["from"]["id"])),
            event_type=TriggerType.CALLBACK,
            payload=str(callback.get("data", "")),
            update_id=update_id,
            callback_id=str(callback_id) if callback_id is not None else None,
        )

    return None  # прочие типы update конструктором пока не поддерживаются
