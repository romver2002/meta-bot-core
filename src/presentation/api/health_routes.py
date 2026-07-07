"""Healthchecks routes (паттерн sro-agent-core)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from application.system.dto import HealthServiceStatus
from application.system.use_cases.get_healthcheck import GetHealthcheckUseCase
from application.system.use_cases.get_services_healthcheck import GetServicesHealthcheckUseCase
from presentation.providers.system import get_healthcheck_uc, get_services_healthcheck_uc

health = APIRouter()


@health.get("/", summary="Проверка состояния meta-bot-core")
async def health_check(
    request: Request,
    use_case: Annotated[GetHealthcheckUseCase, Depends(get_healthcheck_uc)],
) -> HealthServiceStatus:
    return use_case.execute(
        startup_time_service=getattr(request.app.state, "startup_time_service", None),
    )


@health.get("/services/", summary="Отслеживание состояния вспомогательных сервисов")
async def services_health_check(
    use_case: Annotated[GetServicesHealthcheckUseCase, Depends(get_services_healthcheck_uc)],
) -> list[HealthServiceStatus | None]:
    # Авторизация (Security, роль ADMIN — как в sro-agent-core) появится вместе
    # с IAM Admin API: механизм auth — открытый вопрос в current/active-context.md.
    return await use_case.execute()
