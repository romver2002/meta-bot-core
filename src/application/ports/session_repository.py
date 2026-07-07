"""SessionRepository — порт хранилища агрегата Session."""

from __future__ import annotations

from typing import Protocol

from domain.session.entities import Session


class SessionRepository(Protocol):
    """Хранилище FSM-состояний.

    Контракт обеспечивает инвариант «ровно одна активная Session на пару
    (Bot, пользователь)» (memory-bank/domain/domain-model.md): реализация
    гарантирует уникальность на уровне хранилища.
    """

    async def get_active(self, bot_id: str, external_user_id: str) -> Session | None: ...

    async def save(self, session: Session) -> None: ...
