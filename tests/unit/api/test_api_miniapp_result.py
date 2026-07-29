"""Эндпоинт результата mini app: что узнаёт браузер о судьбе результата (BR-012).

Use case подменён заглушкой — проверяется только трансляция исхода движка
в HTTP-код и тело ответа: mini app по ним решает, показывать «готово» или ошибку.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from application.errors import BotNotFoundError, MiniAppAuthError
from application.use_cases.process_update import UpdateOutcome
from presentation.api.admin_routes import admin
from presentation.providers.admin import get_submit_mini_app_result_uc

pytestmark = pytest.mark.unit

_BODY = {"init_data": "signed", "result": {"item": "Latte"}}


class _StubUseCase:
    def __init__(
        self,
        *,
        result: UpdateOutcome = UpdateOutcome.EXECUTED,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error

    async def execute(self, bot_id: str, *args: Any, **kwargs: Any) -> UpdateOutcome:
        if self._error is not None:
            raise self._error
        return self._result


async def _post(use_case: _StubUseCase) -> httpx.Response:
    app = FastAPI()
    app.include_router(admin, prefix="/api")
    app.dependency_overrides[get_submit_mini_app_result_uc] = lambda: use_case
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/bots/bot-1/miniapp/result", json=_BODY)


async def test_executed_result_is_200_ok() -> None:
    response = await _post(_StubUseCase())
    assert response.status_code == 200
    assert response.json() == {"ok": True, "outcome": "executed"}


@pytest.mark.parametrize(
    "outcome",
    [UpdateOutcome.BOT_NOT_PUBLISHED, UpdateOutcome.NO_TRIGGER_MATCHED, UpdateOutcome.FOREIGN_PLATFORM],
)
async def test_not_executed_result_is_409_and_never_ok(outcome: UpdateOutcome) -> None:
    """Бот на паузе или триггера mini_app_result нет — 409, а не «готово» (BR-012).

    Раньше роут отвечал 200 ok=true независимо от исхода: mini app закрывалась
    с успехом, а сценарий не двигался — пользователь ждал ответа, которого нет.
    """
    response = await _post(_StubUseCase(result=outcome))
    assert response.status_code == 409
    assert response.json() == {"ok": False, "outcome": str(outcome)}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(BotNotFoundError("нет бота"), 404), (MiniAppAuthError("подпись не сошлась"), 401)],
)
async def test_errors_keep_their_codes(error: Exception, expected_status: int) -> None:
    response = await _post(_StubUseCase(error=error))
    assert response.status_code == expected_status
