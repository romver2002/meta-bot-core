"""FlowRepository — порт хранилища агрегата Flow."""

from __future__ import annotations

from typing import Protocol

from domain.flow.entities import Flow


class FlowRepository(Protocol):
    """Хранилище агрегата Flow. Реализация — PgFlowRepository (infrastructure/db)."""

    async def get(self, flow_id: str) -> Flow | None: ...

    async def save(self, flow: Flow) -> None: ...
