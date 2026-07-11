"""Идентификаторы из URL: мусорный bot_id — это «не найдено», а не 500.

Не-UUID приходит в PgBotRepository из пути admin/webhook-роутов; репозиторий
обязан ответить None (граница переведёт в 404) до обращения к БД.
"""

from __future__ import annotations

from typing import NoReturn

import pytest

from infrastructure.db.repositories import PgBotRepository

pytestmark = pytest.mark.unit


def _must_not_touch_db() -> NoReturn:
    raise AssertionError("не-UUID id не должен доходить до БД")


async def test_non_uuid_bot_id_resolves_to_none_without_db() -> None:
    repo = PgBotRepository(session_factory=_must_not_touch_db)  # type: ignore[arg-type]

    assert await repo.get("ghost") is None
    assert await repo.get("") is None
    assert await repo.get("../../etc/passwd") is None
