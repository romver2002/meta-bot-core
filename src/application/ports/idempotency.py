"""IdempotencyPort — защита webhook-приёма от повторной доставки (ADR-0004).

Реализация — Redis SET NX EX (infrastructure/cache): TTL перекрывает окна
ретраев обеих платформ (у MAX — до 10 попыток, авто-отписка через 8 часов).
"""

from __future__ import annotations

from typing import Protocol


class IdempotencyPort(Protocol):
    """Отвечает на вопрос «этот ключ виден впервые?» атомарно."""

    async def first_time(self, key: str) -> bool: ...
