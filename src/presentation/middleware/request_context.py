"""HTTP-мидлварь наблюдаемости (ADR-0013): request_id, доступ-лог, единый 500.

Каждому запросу присваивается ``request_id`` (входящий ``X-Request-ID`` или
новый), он же уходит в ответ и во все записи логов через ContextVar.
Необработанное исключение логируется со стеком ровно один раз и превращается
в JSON-500 с ``request_id`` — клиенту есть что назвать при обращении, детали
остаются в логах (наружу стек не отдаём).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from application.observability import bind_request_id

logger = logging.getLogger("app.http")

_CallNext = Callable[[Request], Awaitable[Response]]


async def request_context_middleware(request: Request, call_next: _CallNext) -> Response:
    request_id = bind_request_id(request.headers.get("X-Request-ID"))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except ClientDisconnect:
        # Клиент оборвал соединение — штатное сетевое событие, не ошибка сервиса:
        # errors.log не замусориваем, отвечать уже некому.
        logger.warning(
            "Клиент оборвал соединение",
            extra={"method": request.method, "path": request.url.path},
        )
        return Response(status_code=204, headers={"X-Request-ID": request_id})
    except Exception:
        logger.exception(
            "Необработанное исключение",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    # Healthchecks опрашиваются каждые полминуты — не шумим ими на INFO.
    level = logging.DEBUG if request.url.path.startswith("/healthchecks") else logging.INFO
    logger.log(
        level,
        "HTTP %s %s -> %d",
        request.method,
        request.url.path,
        response.status_code,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response
