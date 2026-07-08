"""HttpxClient — реализация HttpClientPort (блок http_request)."""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from application.ports.http_client import HttpResponse


class HttpxClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        json_body: object | None,
        timeout: float,
    ) -> HttpResponse:
        try:
            response = await self._client.request(
                method,
                url,
                headers=dict(headers),
                json=json_body,
                timeout=timeout,
            )
        except httpx.HTTPError:
            # Сетевой сбой -> status_code=0; движок ветвится на 'error'. Детали
            # (в т.ч. URL с возможными секретами) наружу не пробрасываем.
            return HttpResponse(status_code=0, json=None, text="")
        try:
            payload = response.json()
            data = payload if isinstance(payload, dict) else None
        except ValueError:
            data = None
        return HttpResponse(status_code=response.status_code, json=data, text=response.text)
