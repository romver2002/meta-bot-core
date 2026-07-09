"""Периодический запуск ретеншена ПДн сессий (BR-008, ADR-0011).

Ретеншен — комплаенс-гарантия: его отказ не должен быть молчаливым. Разовый
сбой не убивает цикл, но каждый виден в логах; ненулевой проход логируется.
Остановка — отменой задачи (CancelledError не подавляется).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from application.use_cases.purge_expired_sessions import PurgeExpiredSessionsUseCase

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


async def run_periodic_purge(
    purge: PurgeExpiredSessionsUseCase,
    interval_seconds: float,
    *,
    now: Callable[[], datetime] = _utc_now,
) -> None:
    """Гоняет чистку раз в ``interval_seconds`` до отмены задачи."""
    while True:
        try:
            report = await purge.execute(now())
            if report.expired or report.deleted:
                logger.info(
                    "Ретеншен сессий (BR-008): просрочено %d, удалено %d",
                    report.expired,
                    report.deleted,
                )
        except Exception:
            logger.exception("Проход ретеншена сессий не выполнен — повтор через интервал")
        await asyncio.sleep(interval_seconds)
