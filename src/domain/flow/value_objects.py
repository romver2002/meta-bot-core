"""Value objects агрегата Flow.

Закрытые перечни типов — проекция каталога блоков
memory-bank/domain/flow-blocks.md: новый тип блока/триггера добавляется
строкой в каталог, значением в перечень, реализацией и тестом в одном PR.
"""

from __future__ import annotations

import enum


class NodeType(enum.StrEnum):
    """Типы блоков сценария. Node — данные (тип + параметры), а не код."""

    SEND_MESSAGE = "send_message"
    SHOW_BUTTONS = "show_buttons"
    ASK = "ask"
    CONDITION = "condition"
    OPEN_MINI_APP = "open_mini_app"
    SAVE = "save"
    HTTP_REQUEST = "http_request"
    NOTIFY = "notify"
    CUSTOM_CODE = "custom_code"


class TriggerType(enum.StrEnum):
    """Типы входов в сценарий."""

    START = "start"
    TEXT = "text"
    CALLBACK = "callback"
    MINI_APP_RESULT = "mini_app_result"
    # Системный вход «внешняя система → сценарий» (ADR-0017, BR-010):
    # POST /api/bots/{id}/events; матчинг — по точному имени события в config["event"]
    EXTERNAL_EVENT = "external_event"


class ButtonAction(enum.StrEnum):
    """Действия кнопки: единая модель, платформенное представление — в адаптере."""

    OPEN_MINI_APP = "open_mini_app"
    CALLBACK = "callback"
    URL = "url"
    NEXT = "next"
