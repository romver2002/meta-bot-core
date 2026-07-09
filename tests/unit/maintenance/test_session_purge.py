"""Демон-цикл ретеншена (BR-008): переживает сбой прохода, останавливается отменой."""

from __future__ import annotations

import asyncio
import datetime

import pytest

from infrastructure.maintenance.session_purge import run_periodic_purge

pytestmark = pytest.mark.unit


class _Report:
    expired, deleted = 1, 0


class _FlakyPurge:
    """Первый проход падает; сигналит Event при достижении target вызовов."""

    def __init__(self, target: int, *, fail_first: bool = True) -> None:
        self.calls = 0
        self.target = target
        self.fail_first = fail_first
        self.reached = asyncio.Event()

    async def execute(self, now: datetime.datetime) -> _Report:
        self.calls += 1
        if self.calls >= self.target:
            self.reached.set()
        if self.calls == 1 and self.fail_first:
            raise RuntimeError("БД недоступна")
        return _Report()


async def test_single_failure_does_not_kill_loop() -> None:
    purge = _FlakyPurge(target=3)
    task = asyncio.create_task(run_periodic_purge(purge, 0))  # type: ignore[arg-type]

    await asyncio.wait_for(purge.reached.wait(), timeout=5)  # первый упал — циклы идут
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert purge.calls >= 3


async def test_cancellation_stops_loop_promptly() -> None:
    purge = _FlakyPurge(target=1, fail_first=False)
    task = asyncio.create_task(run_periodic_purge(purge, 3600))  # type: ignore[arg-type]
    await asyncio.wait_for(purge.reached.wait(), timeout=5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task  # CancelledError не подавлен — остановка штатная

    assert purge.calls == 1  # долгий интервал: новых проходов после отмены нет
