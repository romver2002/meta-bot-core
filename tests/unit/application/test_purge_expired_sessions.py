"""PurgeExpiredSessionsUseCase — ретеншен ПДн сессий (BR-008, ADR-0011)."""

from __future__ import annotations

import datetime

import pytest

from application.use_cases.purge_expired_sessions import PurgeExpiredSessionsUseCase

pytestmark = pytest.mark.unit


class _SpyRetention:
    def __init__(self) -> None:
        self.expire_cutoffs: list[datetime.datetime] = []
        self.delete_cutoffs: list[datetime.datetime] = []

    async def expire_idle(self, cutoff: datetime.datetime) -> int:
        self.expire_cutoffs.append(cutoff)
        return 2

    async def delete_finished_before(self, cutoff: datetime.datetime) -> int:
        self.delete_cutoffs.append(cutoff)
        return 3


async def test_cutoffs_follow_policy_and_report_counts() -> None:
    spy = _SpyRetention()
    use_case = PurgeExpiredSessionsUseCase(
        spy, idle_ttl_seconds=3600, retention_seconds=30 * 86400
    )
    now = datetime.datetime(2026, 7, 10, 12, 0, tzinfo=datetime.UTC)

    report = await use_case.execute(now)

    assert spy.expire_cutoffs == [now - datetime.timedelta(hours=1)]
    assert spy.delete_cutoffs == [now - datetime.timedelta(days=30)]
    assert (report.expired, report.deleted) == (2, 3)
