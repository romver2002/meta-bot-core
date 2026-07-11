"""Контекст корреляции запросов (ADR-0013).

``request_id`` связывает все записи логов одного HTTP-запроса/вебхука.
Живёт в application-слое, чтобы его могли импортировать и presentation
(middleware ставит значение), и infrastructure (фильтр логов читает), —
без нарушения направления зависимостей. Чистый stdlib, без фреймворков.
"""

from __future__ import annotations

import contextvars
import re
import uuid

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

# Клиентский X-Request-ID — недоверенный ввод: попадает в каждую строку логов,
# поэтому ограничиваем алфавит и длину; мусор заменяем сгенерированным id.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_request_id() -> str:
    """Короткий идентификатор корреляции (12 hex — достаточно для поиска в логах)."""
    return uuid.uuid4().hex[:12]


def bind_request_id(value: str | None) -> str:
    """Ставит request_id текущего контекста; пустое/мусорное значение — генерирует новый."""
    candidate = (value or "").strip()
    rid = candidate if _VALID_REQUEST_ID.fullmatch(candidate) else new_request_id()
    request_id_var.set(rid)
    return rid


def current_request_id() -> str | None:
    return request_id_var.get()
