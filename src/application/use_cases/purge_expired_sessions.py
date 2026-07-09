"""PurgeExpiredSessionsUseCase — ретеншен ПДн сессий (BR-008, ADR-0011).

Двухступенчатое стирание:
1. активная сессия без событий дольше idle-TTL -> expired, переменные стёрты
   (заодно освобождает пару (Bot, user) от зависшего FSM);
2. завершённая/просроченная сессия старше срока хранения -> строка удаляется
   целиком, включая ``external_user_id``/``external_chat_id`` (тоже ПДн).

Запускается фоновой задачей composition root (интервал — конфигурация).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

from application.ports.session_repository import SessionRetentionPort


@dataclasses.dataclass(frozen=True, slots=True)
class PurgeReport:
    """Итог одного прохода чистки (для наблюдаемости)."""

    expired: int
    deleted: int


class PurgeExpiredSessionsUseCase:
    """Стирает ПДн сессий по политике ретеншена.

    ``now`` передаётся вызывающим (детерминизм в тестах, отсутствие
    обращения к часам в application-слое).
    """

    def __init__(
        self,
        sessions: SessionRetentionPort,
        *,
        idle_ttl_seconds: int,
        retention_seconds: int,
    ) -> None:
        self._sessions = sessions
        self._idle_ttl = timedelta(seconds=idle_ttl_seconds)
        self._retention = timedelta(seconds=retention_seconds)

    async def execute(self, now: datetime) -> PurgeReport:
        expired = await self._sessions.expire_idle(now - self._idle_ttl)
        deleted = await self._sessions.delete_finished_before(now - self._retention)
        return PurgeReport(expired=expired, deleted=deleted)
