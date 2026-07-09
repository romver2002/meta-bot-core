"""Парсинг MAX update -> IncomingEvent (ADR-0004, dev.max.ru/docs-api).

Наружу уходит только платформонезависимый IncomingEvent.

Идемпотентность: у MAX НЕТ сквозного update_id, а доставка ретраится до 10 раз
(specs/002-platform-deep-dive). Ключ дедупликации синтезируем из стабильных
per-объектных полей: ``message.body.mid`` для сообщений, ``callback.callback_id``
для колбэков; для прочих типов — составной ключ. Поле ``seq`` НЕ использовать —
оно уникально лишь в пределах чата.

Набор update-типов MAX расширяемый: неизвестный тип не должен ронять приём,
для него возвращаем None (игнор), а не исключение.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, cast

from domain.bot.value_objects import Platform
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType


def _composite_key(update_type: str, *parts: object) -> str:
    """Резервный ключ идемпотентности, когда нет mid/callback_id.

    Части (timestamp, user_id — ПДн) хэшируются: ключ попадает в Redis,
    а внешние идентификаторы пользователей в хранилищах не светим (BR-008).
    """
    raw = ":".join(str(p) for p in parts if p is not None)
    return f"{update_type}:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def parse_max_update(bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
    update_type = str(payload.get("update_type", ""))
    timestamp = payload.get("timestamp")

    if update_type in {"message_created", "message_edited"}:
        message = cast("dict[str, Any]", payload.get("message") or {})
        sender = cast("dict[str, Any]", message.get("sender") or {})
        recipient = cast("dict[str, Any]", message.get("recipient") or {})
        body = cast("dict[str, Any]", message.get("body") or {})
        text = str(body.get("text", ""))
        mid = body.get("mid")
        return IncomingEvent(
            platform=Platform.MAX,
            bot_id=bot_id,
            external_user_id=str(sender.get("user_id", "")),
            external_chat_id=str(recipient.get("chat_id", sender.get("user_id", ""))),
            event_type=TriggerType.START if text.startswith("/start") else TriggerType.TEXT,
            text=text,
            update_id=str(mid) if mid is not None else _composite_key(update_type, timestamp, sender.get("user_id")),
        )

    if update_type == "message_callback":
        callback = cast("dict[str, Any]", payload.get("callback") or {})
        user = cast("dict[str, Any]", callback.get("user") or {})
        message = cast("dict[str, Any]", payload.get("message") or {})
        recipient = cast("dict[str, Any]", message.get("recipient") or {})
        callback_id = callback.get("callback_id")
        return IncomingEvent(
            platform=Platform.MAX,
            bot_id=bot_id,
            external_user_id=str(user.get("user_id", "")),
            external_chat_id=str(recipient.get("chat_id", user.get("user_id", ""))),
            event_type=TriggerType.CALLBACK,
            payload=str(callback.get("payload", "")),
            update_id=str(callback_id)
            if callback_id is not None
            else _composite_key(update_type, timestamp, user.get("user_id")),
            callback_id=str(callback_id) if callback_id is not None else None,
        )

    if update_type == "bot_started":
        user = cast("dict[str, Any]", payload.get("user") or {})
        chat_id = payload.get("chat_id", user.get("user_id"))
        return IncomingEvent(
            platform=Platform.MAX,
            bot_id=bot_id,
            external_user_id=str(user.get("user_id", "")),
            external_chat_id=str(chat_id),
            event_type=TriggerType.START,
            update_id=_composite_key(update_type, timestamp, user.get("user_id")),
        )

    return None  # прочие/неизвестные типы конструктором пока не обрабатываются
