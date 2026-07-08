"""Единый webhook-вход платформ (ADR-0004).

Pipeline: приём -> проверка секрета -> нормализация адаптером в IncomingEvent ->
идемпотентность (Redis SET NX) -> Flow Engine. Ответ всегда 200 OK на понятные
события — иначе платформы устраивают ретраи-штормы (MAX авто-отписывает бота
после 8 часов без 200).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from application.errors import ApplicationError
from application.ports.bot_platform import PlatformFactory
from application.ports.idempotency import IdempotencyPort
from application.use_cases.process_update import ProcessUpdateUseCase
from domain.bot.value_objects import Platform
from presentation.providers.webhooks import (
    get_idempotency,
    get_platform_factory,
    get_process_update_uc,
)

webhooks = APIRouter()

_SECRET_HEADERS = {
    Platform.TELEGRAM: "X-Telegram-Bot-Api-Secret-Token",
    Platform.MAX: "X-Max-Bot-Api-Secret",
}


@webhooks.post("/{platform}/{bot_id}", summary="Приём update платформы")
async def receive_update(
    platform: str,
    bot_id: str,
    request: Request,
    factory: Annotated[PlatformFactory, Depends(get_platform_factory)],
    idempotency: Annotated[IdempotencyPort, Depends(get_idempotency)],
    use_case: Annotated[ProcessUpdateUseCase, Depends(get_process_update_uc)],
) -> dict[str, Any]:
    try:
        platform_vo = Platform(platform)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Неизвестная платформа") from exc

    expected_secret = request.app.state.settings.webhook_secret
    if expected_secret and request.headers.get(_SECRET_HEADERS[platform_vo]) != expected_secret:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Неверный секрет вебхука")

    payload = await request.json()
    event = factory.for_platform(platform_vo).parse_update(bot_id, payload)
    if event is None:
        return {"ok": True, "ignored": True}

    if event.update_id is not None:
        key = f"idemp:{platform_vo.value}:{bot_id}:{event.update_id}"
        if not await idempotency.first_time(key):
            return {"ok": True, "duplicate": True}

    try:
        await use_case.execute(event)
    except ApplicationError:
        # Событие принято, но не обработано (бот удалён и т.п.) — 200,
        # чтобы платформа не долбила ретраями; детали — в логи (observability).
        return {"ok": True, "processed": False}
    return {"ok": True}
