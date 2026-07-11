"""Схемы ответов вебхук-роутов (ADR-0013).

Исход приёма update — закрытый перечень, а не словари-литералы по коду:
контракт видно в одном месте, OpenAPI его документирует, опечатка в ключе
невозможна. ``ok`` всегда True — платформам отвечаем 200 на понятные события,
иначе они устраивают ретраи-штормы (MAX авто-отписывает после 8 ч без 200).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel


class WebhookOutcome(enum.StrEnum):
    """Исход приёма update."""

    PROCESSED = "processed"  # событие исполнено движком
    IGNORED = "ignored"  # тип update конструктором не поддерживается
    DUPLICATE = "duplicate"  # отброшен идемпотентностью (ретрай платформы)
    NOT_PROCESSED = "not_processed"  # принят, но не обработан (детали — в логе)


class WebhookAck(BaseModel):
    ok: bool = True
    outcome: WebhookOutcome
