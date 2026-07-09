"""Сущности агрегата Session.

Session — FSM-состояние пользователя: текущий шаг сценария + переменные.
Инвариант «ровно одна активная Session на пару (Bot, пользователь)»
пересекает границу агрегата и обеспечивается контрактом SessionRepository
(уникальность в хранилище), а не объектной ссылкой.

Жизненный цикл: active -> completed (сценарий дошёл до конца) | expired
(вытеснена по TTL). Завершённая сессия освобождает пару (Bot, пользователь):
следующий триггер начнёт новую сессию уже на актуальной опубликованной
версии сценария (ADR-0008).
"""

from __future__ import annotations

import dataclasses
import enum

from domain.errors import SessionStateError


class SessionStatus(enum.StrEnum):
    """Статус FSM-сессии."""

    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclasses.dataclass(slots=True)
class Session:
    """FSM пользователя в сценарии бота. Ссылки на Bot — по идентификатору.

    ``external_user_id`` и ``variables`` — ПДн: исключены из repr, чтобы
    не утекали в логи (аналогично маскировке Token.__repr__).
    """

    id: str
    bot_id: str
    external_user_id: str = dataclasses.field(repr=False)
    flow_version_id: str | None = None
    current_node_id: str | None = None
    variables: dict[str, object] = dataclasses.field(default_factory=dict, repr=False)
    awaiting_variable: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE

    def advance(self, node_id: str) -> None:
        """Переходит к следующему шагу сценария и снимает ожидание ответа."""
        self._ensure_active()
        self.current_node_id = node_id
        self.awaiting_variable = None

    def await_answer(self, save_as: str) -> None:
        """Блок ask: переводит FSM в ожидание ответа пользователя."""
        self._ensure_active()
        if not save_as:
            raise SessionStateError("Блоку ask нужно имя переменной для ответа (save_as)")
        self.awaiting_variable = save_as

    def submit_answer(self, value: object) -> None:
        """Принимает ответ пользователя, сохраняя его в ожидаемую переменную."""
        if self.awaiting_variable is None:
            raise SessionStateError("Сессия не ожидает ответа пользователя")
        self.variables[self.awaiting_variable] = value
        self.awaiting_variable = None

    def remember(self, key: str, value: object) -> None:
        """Блок save: записывает значение в переменные сценария."""
        self.variables[key] = value

    def complete(self) -> None:
        """Сценарий дошёл до конца: сессия завершена, пара (Bot, user) свободна.

        Переменные стираются (BR-008, минимизация ПДн): данные сценария живут
        не дольше самой сессии — все сайд-эффекты (ответы, уведомления) уже
        выполнены к моменту завершения.
        """
        self.awaiting_variable = None
        self.variables.clear()
        self.status = SessionStatus.COMPLETED

    def expire(self) -> None:
        """Вытеснение по TTL/решению оператора. Переменные стираются (BR-008)."""
        self.awaiting_variable = None
        self.variables.clear()
        self.status = SessionStatus.EXPIRED

    def _ensure_active(self) -> None:
        if self.status is not SessionStatus.ACTIVE:
            raise SessionStateError(f"Сессия {self.id} не активна: {self.status}")
