"""HttpClientPort — порт исходящих HTTP-вызовов для блока http_request.

Генеричный: движок дергает ЛЮБОЙ внешний HTTP-API (CRM, LLM, погода, оплата),
не зная про конкретный сервис — URL/заголовки/тело приходят данными узла.
Реализация — HttpxClient (infrastructure/http).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Protocol


@dataclasses.dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    json: dict[str, Any] | None
    text: str


class HttpClientPort(Protocol):
    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        json_body: object | None,
        timeout: float,
    ) -> HttpResponse:
        """Выполняет запрос.

        Сетевые сбои реализация оборачивает в HttpResponse со ``status_code=0``
        (движок трактует это как ошибку и ветвится на 'error').
        """
        ...
