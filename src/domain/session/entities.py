"""Сущности агрегата Session.

Session — FSM-состояние пользователя: текущий шаг сценария + переменные.
Инвариант «ровно одна активная Session на пару (Bot, пользователь)»
пересекает границу агрегата и обеспечивается контрактом SessionRepository
(уникальность в хранилище), а не объектной ссылкой.
"""

from __future__ import annotations

import dataclasses

from domain.errors import SessionStateError


@dataclasses.dataclass(slots=True)
class Session:
    """FSM пользователя в сценарии бота. Ссылки на Bot — по идентификатору."""

    id: str
    bot_id: str
    external_user_id: str
    flow_version_id: str | None = None
    current_node_id: str | None = None
    variables: dict[str, object] = dataclasses.field(default_factory=dict)
    awaiting_variable: str | None = None

    def advance(self, node_id: str) -> None:
        """Переходит к следующему шагу сценария и снимает ожидание ответа."""
        self.current_node_id = node_id
        self.awaiting_variable = None

    def await_answer(self, save_as: str) -> None:
        """Блок ask: переводит FSM в ожидание ответа пользователя."""
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
