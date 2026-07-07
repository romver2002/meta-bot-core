"""Build dependent services healthcheck responses (паттерн sro-agent-core)."""

from __future__ import annotations

from http import HTTPStatus

from application.ports.health import (
    HealthServiceProbe,
    HealthServiceProbeResult,
    HealthServiceRegistry,
    HealthServiceTarget,
)
from application.system.dto import HealthServiceStatus


class GetServicesHealthcheckUseCase:
    def __init__(self, *, registry: HealthServiceRegistry, probe: HealthServiceProbe) -> None:
        self._registry = registry
        self._probe = probe

    async def execute(self) -> list[HealthServiceStatus | None]:
        return [await self._check_target(target) for target in self._registry.list_targets()]

    async def _check_target(self, target: HealthServiceTarget) -> HealthServiceStatus | None:
        try:
            result = await self._probe.check(target)
            if result is None:
                return None
            return self._to_status(result)
        except Exception as exc:  # noqa: BLE001 - health endpoint reports per-service errors
            return HealthServiceStatus(
                service=target.name,
                url=target.domain,
                status_code=None,
                error=str(exc),
                status=HTTPStatus.BAD_REQUEST,
                info=None,
            )

    @staticmethod
    def _to_status(result: HealthServiceProbeResult) -> HealthServiceStatus:
        return HealthServiceStatus(
            service=result.service,
            url=result.url,
            status_code=result.status_code,
            startup_time_service=result.startup_time_service,
            error=result.error,
            version=result.version,
            status=result.status,
            info=dict(result.info) if result.info is not None else None,
        )
