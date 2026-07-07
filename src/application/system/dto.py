"""System DTOs (паттерн sro-agent-core)."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from typing import Any

from pydantic import BaseModel


class HealthServiceStatus(BaseModel):
    service: str
    url: str | None = None
    status_code: int | None = None
    startup_time_service: datetime | str | None = None
    error: str | None = None
    version: str | None = None
    status: HTTPStatus | None = None
    info: dict[str, Any] | None = None
