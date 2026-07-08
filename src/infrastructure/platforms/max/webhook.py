"""Парсинг MAX update -> IncomingEvent (ADR-0004, dev.max.ru/docs-api).

update_type: bot_started | message_created | message_callback; наружу уходит
только платформонезависимый IncomingEvent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from domain.bot.value_objects import Platform
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType


def parse_max_update(bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
    update_type = str(payload.get("update_type", ""))
    # Собственного update_id у MAX нет — ключ идемпотентности собирается
    # из типа и таймстемпа доставки (стабилен между ретраями).
    timestamp = payload.get("timestamp")
    update_id = f"{update_type}:{timestamp}" if timestamp is not None else None

    if update_type == "bot_started":
        user = cast("dict[str, Any]", payload.get("user") or {})
        chat_id = payload.get("chat_id", user.get("user_id"))
        return IncomingEvent(
            platform=Platform.MAX,
            bot_id=bot_id,
            external_user_id=str(user.get("user_id", "")),
            external_chat_id=str(chat_id),
            event_type=TriggerType.START,
            update_id=update_id,
        )

    if update_type == "message_created":
        message = cast("dict[str, Any]", payload.get("message") or {})
        sender = cast("dict[str, Any]", message.get("sender") or {})
        recipient = cast("dict[str, Any]", message.get("recipient") or {})
        body = cast("dict[str, Any]", message.get("body") or {})
        text = str(body.get("text", ""))
        return IncomingEvent(
            platform=Platform.MAX,
            bot_id=bot_id,
            external_user_id=str(sender.get("user_id", "")),
            external_chat_id=str(recipient.get("chat_id", sender.get("user_id", ""))),
            event_type=TriggerType.START if text.startswith("/start") else TriggerType.TEXT,
            text=text,
            update_id=update_id,
        )

    if update_type == "message_callback":
        callback = cast("dict[str, Any]", payload.get("callback") or {})
        user = cast("dict[str, Any]", callback.get("user") or {})
        message = cast("dict[str, Any]", payload.get("message") or {})
        recipient = cast("dict[str, Any]", message.get("recipient") or {})
        return IncomingEvent(
            platform=Platform.MAX,
            bot_id=bot_id,
            external_user_id=str(user.get("user_id", "")),
            external_chat_id=str(recipient.get("chat_id", user.get("user_id", ""))),
            event_type=TriggerType.CALLBACK,
            payload=str(callback.get("payload", "")),
            update_id=update_id,
        )

    return None
