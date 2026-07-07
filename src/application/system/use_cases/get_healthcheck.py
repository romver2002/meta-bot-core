"""Build current service healthcheck response (паттерн sro-agent-core)."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from importlib.metadata import PackageNotFoundError, version

from application.system.dto import HealthServiceStatus


def get_app_version(project_name: str) -> str:
    try:
        return version(project_name)
    except PackageNotFoundError:
        return "unknown"


class GetHealthcheckUseCase:
    def __init__(self, *, project_name: str, url: str) -> None:
        self._project_name = project_name
        self._url = url

    def execute(self, *, startup_time_service: datetime | str | None) -> HealthServiceStatus:
        return HealthServiceStatus(
            service=self._project_name,
            url=self._url,
            status_code=HTTPStatus.OK,
            startup_time_service=startup_time_service,
            version=get_app_version(self._project_name),
            status=HTTPStatus.OK,
            info={},
        )
