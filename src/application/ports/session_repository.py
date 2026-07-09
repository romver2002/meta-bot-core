"""SessionRepository — порт хранилища агрегата Session."""

from __future__ import annotations

import datetime
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


class SessionRetentionPort(Protocol):
    """Ретеншен ПДн сессий (BR-008): просрочка и стирание в хранилище.

    Отдельный порт (ISP): движку он не нужен — только фоновой чистке.
    """

    async def expire_idle(self, cutoff: datetime.datetime) -> int:
        """Активные сессии без событий с ``cutoff`` -> expired, переменные стёрты.

        :returns: число просроченных сессий.
        """
        ...

    async def delete_finished_before(self, cutoff: datetime.datetime) -> int:
        """Удаляет завершённые/просроченные сессии старше ``cutoff`` целиком —
        вместе с ``external_user_id``/``external_chat_id`` (тоже ПДн).

        :returns: число удалённых строк.
        """
        ...
