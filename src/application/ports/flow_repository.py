"""FlowRepository — порт хранилища агрегата Flow (версионированный, ADR-0008).

Черновик правится in-place (с оптимистическим локом), публикация замораживает
его в иммутабельную версию. Реализация — PgFlowRepository (infrastructure/db).
"""

from __future__ import annotations

from typing import Protocol

from domain.flow.entities import Flow
from domain.flow.version import FlowVersion


class FlowRepository(Protocol):
    """Хранилище сценариев: черновик + иммутабельные published-версии."""

    async def get_draft(self, flow_id: str) -> Flow | None:
        """Возвращает редактируемый черновик сценария."""
        ...

    async def save_draft(self, flow: Flow, *, expected_row_version: int | None = None) -> int:
        """Сохраняет черновик in-place; возвращает новый row_version.

        :raises application.errors.ConcurrencyError: черновик изменён
            конкурентно (``expected_row_version`` устарел).
        """
        ...

    async def publish(self, flow_id: str) -> FlowVersion:
        """Замораживает черновик в новую иммутабельную published-версию.

        Инварианты публикации (BR-001/BR-006) проверяет домен ДО вызова.
        """
        ...

    async def get_version(self, flow_version_id: str) -> FlowVersion | None:
        """Иммутабельный снапшот (для рантайма и активных Session)."""
        ...

    async def list_versions(self, flow_id: str) -> list[FlowVersion]:
        """История версий сценария (для UI и отката)."""
        ...
