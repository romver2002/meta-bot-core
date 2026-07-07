"""Системные use case'ы health (паттерн sro-agent-core)."""

from http import HTTPStatus

import pytest

from application.ports.health import HealthServiceProbeResult, HealthServiceTarget
from application.system.use_cases.get_healthcheck import GetHealthcheckUseCase, get_app_version
from application.system.use_cases.get_services_healthcheck import GetServicesHealthcheckUseCase

pytestmark = pytest.mark.unit


def test_healthcheck_reports_service_and_version() -> None:
    use_case = GetHealthcheckUseCase(project_name="meta-bot-core", url="http://localhost:8000")
    status = use_case.execute(startup_time_service="2026-07-08T12:00:00+03:00")
    assert status.service == "meta-bot-core"
    assert status.status is HTTPStatus.OK
    assert status.version == get_app_version("meta-bot-core")
    assert status.startup_time_service == "2026-07-08T12:00:00+03:00"


def test_app_version_unknown_for_missing_package() -> None:
    assert get_app_version("no-such-package-xyz") == "unknown"


class _Registry:
    def __init__(self, targets: list[HealthServiceTarget]) -> None:
        self._targets = targets

    def list_targets(self) -> list[HealthServiceTarget]:
        return self._targets


class _Probe:
    """ok -> OK; boom -> исключение; skip -> None (нечего проверять)."""

    async def check(self, target: HealthServiceTarget) -> HealthServiceProbeResult | None:
        if target.kind == "boom":
            msg = "connection refused"
            raise ConnectionError(msg)
        if target.kind == "skip":
            return None
        return HealthServiceProbeResult(
            service=target.name, url=target.domain, status_code=200, status=HTTPStatus.OK, info={}
        )


async def test_services_healthcheck_reports_ok_error_and_skip() -> None:
    registry = _Registry(
        [
            HealthServiceTarget(name="postgres", kind="postgres", domain="postgres:5432"),
            HealthServiceTarget(name="redis", kind="boom", domain="redis:6379"),
            HealthServiceTarget(name="nothing", kind="skip"),
        ]
    )
    use_case = GetServicesHealthcheckUseCase(registry=registry, probe=_Probe())

    statuses = await use_case.execute()

    assert len(statuses) == 3
    ok, failed, skipped = statuses
    assert ok is not None
    assert ok.status is HTTPStatus.OK
    assert ok.service == "postgres"
    assert failed is not None
    assert failed.status is HTTPStatus.BAD_REQUEST
    assert failed.error is not None
    assert "connection refused" in failed.error
    assert skipped is None
