"""Жизненный цикл Session: минимизация ПДн при завершении/просрочке (BR-008).

Эти тесты — исполняемая спецификация стирания: bulk-SQL
``PgSessionRepository.expire_idle`` обязан зеркалить ``Session.expire()``.
"""

from __future__ import annotations

import pytest

from domain.errors import SessionStateError
from domain.session.entities import Session, SessionStatus

pytestmark = pytest.mark.unit


def _session_with_pii() -> Session:
    session = Session(id="s1", bot_id="b1", external_user_id="u1")
    session.remember("req_name", "Иван")
    session.await_answer("req_contact")
    return session


def test_complete_erases_variables_and_awaiting() -> None:
    session = _session_with_pii()

    session.complete()

    assert session.status is SessionStatus.COMPLETED
    assert session.variables == {}
    assert session.awaiting_variable is None


def test_expire_erases_variables_and_awaiting() -> None:
    session = _session_with_pii()

    session.expire()

    assert session.status is SessionStatus.EXPIRED
    assert session.variables == {}
    assert session.awaiting_variable is None


def test_finished_session_rejects_further_steps() -> None:
    session = _session_with_pii()
    session.expire()

    with pytest.raises(SessionStateError):
        session.advance("any-node")
