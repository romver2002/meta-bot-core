"""Порты health-проверок вспомогательных сервисов (паттерн sro-agent-core).

Registry перечисляет цели, Probe опрашивает одну цель; реализации — в
infrastructure/integrations/health_checks.py.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from http import HTTPStatus
from typing import Protocol


@dataclasses.dataclass(frozen=True, slots=True)
class HealthServiceTarget:
    """Цель проверки: инфраструктурный или HTTP-сервис."""

    name: str
    kind: str  # postgres | redis | http
    domain: str | None = None  # БЕЗ учётных данных — попадает в ответ health
    health: str | None = None  # путь health-эндпоинта для kind=http


@dataclasses.dataclass(frozen=True, slots=True)
class HealthServiceProbeResult:
    """Результат опроса одной цели."""

    service: str
    url: str | None = None
    status_code: int | None = None
    startup_time_service: datetime | str | None = None
    error: str | None = None
    version: str | None = None
    status: HTTPStatus | None = None
    info: dict[str, object] | None = None


class HealthServiceRegistry(Protocol):
    """Реестр целей для /healthchecks/services/."""

    def list_targets(self) -> list[HealthServiceTarget]: ...


class HealthServiceProbe(Protocol):
    """Опрашивает одну цель; None — цель нечего проверять."""

    async def check(self, target: HealthServiceTarget) -> HealthServiceProbeResult | None: ...
