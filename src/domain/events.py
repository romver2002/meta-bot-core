"""Доменные события meta-bot-core.

IncomingEvent — единая платформонезависимая модель входящего события:
к ней платформенный адаптер (infrastructure/platforms/*/webhook.py)
нормализует любой update; application работает только с ней
(memory-bank/architecture/overview.md, ADR-0004).
"""

from __future__ import annotations

import dataclasses

from domain.bot.value_objects import Platform
from domain.flow.value_objects import TriggerType


@dataclasses.dataclass(frozen=True, slots=True)
class IncomingEvent:
    """Нормализованное входящее событие платформы.

    ``platform`` здесь — данные о происхождении события, а не повод для
    ветвления: бизнес-логика по платформе не ветвится (BR-005).
    """

    platform: Platform
    bot_id: str
    external_user_id: str
    external_chat_id: str
    event_type: TriggerType
    text: str | None = None
    payload: str | None = None
    update_id: str | None = None  # идентификатор update платформы — ключ идемпотентности


@dataclasses.dataclass(frozen=True, slots=True)
class ButtonClicked:
    """Пользователь нажал кнопку (callback)."""

    bot_id: str
    external_user_id: str
    payload: str


@dataclasses.dataclass(frozen=True, slots=True)
class MiniAppOpened:
    """Пользователь открыл mini app бота."""

    bot_id: str
    external_user_id: str
    mini_app_id: str
