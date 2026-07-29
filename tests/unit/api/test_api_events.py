"""Эндпоинт внешних событий: что именно узнаёт вызывающий (ADR-0017, BR-010).

Здесь проверяется ТОЛЬКО трансляция ошибок use case в HTTP-коды — сам use case
подменён заглушкой. Для внешнего сервиса (радар, CRM) эти коды и есть контракт:
по ним он решает, ретраить, чинить запрос или звать человека.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from application.errors import (
    ApplicationError,
    BotNotFoundError,
    ExternalEventAuthError,
    ExternalEventValidationError,
)
from application.use_cases.submit_external_event import ExternalEventOutcome
from presentation.api.admin_routes import admin
from presentation.providers.admin import get_submit_external_event_uc

pytestmark = pytest.mark.unit

_BODY = {"event": "freelance_project", "to": {"role": "owner"}, "payload": {"title": "Заказ"}}


class _StubUseCase:
    def __init__(
        self,
        *,
        result: ExternalEventOutcome = ExternalEventOutcome.DELIVERED,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error

    async def execute(self, bot_id: str, **kwargs: Any) -> ExternalEventOutcome:
        if self._error is not None:
            raise self._error
        return self._result


def _client(use_case: _StubUseCase) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(admin, prefix="/api")
    app.dependency_overrides[get_submit_external_event_uc] = lambda: use_case
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _post(use_case: _StubUseCase) -> httpx.Response:
    async with _client(use_case) as client:
        return await client.post("/api/bots/bot-1/events", json=_BODY, headers={"X-Events-Token": "t"})


async def test_delivered_event_is_200() -> None:
    response = await _post(_StubUseCase())
    assert response.status_code == 200
    assert response.json() == {"delivered": True, "outcome": "delivered", "retriable": False}


async def test_duplicate_event_is_200_with_delivered_false() -> None:
    """Дубль по event_id — не ошибка: ретрай вызывающего отработал штатно."""
    response = await _post(_StubUseCase(result=ExternalEventOutcome.DUPLICATE))
    assert response.status_code == 200
    assert response.json() == {"delivered": False, "outcome": "duplicate", "retriable": False}


@pytest.mark.parametrize(
    ("outcome", "retriable"),
    [
        (ExternalEventOutcome.IN_FLIGHT, True),
        (ExternalEventOutcome.BOT_NOT_PUBLISHED, True),
        (ExternalEventOutcome.NO_TRIGGER_MATCHED, False),
    ],
)
async def test_not_executed_event_is_409_and_never_delivered(outcome: ExternalEventOutcome, retriable: bool) -> None:
    """Сценарий событие не исполнил — 409 и delivered=false (ADR-0019).

    Раньше все эти случаи приезжали как 200 delivered=true: отправитель помечал
    карточку доставленной, хотя её никто не получил и уже не получит.
    """
    response = await _post(_StubUseCase(result=outcome))
    assert response.status_code == 409
    assert response.json() == {"delivered": False, "outcome": str(outcome), "retriable": retriable}


async def test_platform_refusal_is_502_not_500() -> None:
    """Отказ платформы — 502, как у publish, а не «внутренняя ошибка».

    Живой прогон 2026-07-26: MAX отвечает 404, пока получатель не открыл диалог
    с ботом. Под 500 это выглядит как «сервер моргнул, повтори» — вызывающий
    будет ретраить вечно, хотя чинится только действием человека.
    """
    response = await _post(_StubUseCase(error=ApplicationError("MAX message не доставлен (chat=user:1)")))
    assert response.status_code == 502
    assert "MAX message не доставлен" in response.json()["detail"]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ExternalEventAuthError("нет токена"), 401),
        (BotNotFoundError("нет бота"), 404),
        (ExternalEventValidationError("роль не привязана"), 422),
    ],
)
async def test_specific_errors_keep_their_codes_under_the_502_branch(error: Exception, expected_status: int) -> None:
    """Все три — наследники ApplicationError: порядок except в роуте значим.

    Если ветку 502 однажды поднимут выше, 401/404/422 молча схлопнутся в 502,
    и вызывающий перестанет отличать «протух токен» от «упала платформа».
    """
    response = await _post(_StubUseCase(error=error))
    assert response.status_code == expected_status
