"""FlowRepository — порт хранилища агрегата Flow (версионированный, ADR-0008).

Черновик правится in-place под оптимистическим локом; публикация замораживает
его в иммутабельную версию. Снапшот черновика (``FlowDraft``) несёт
``row_version`` — токен конкуренции, который клиент обязан вернуть при
сохранении и публикации (защита от TOCTOU: замораживается ровно тот черновик,
который прошёл валидацию BR-001/BR-006).
"""

from __future__ import annotations

import dataclasses
from typing import Protocol

from domain.flow.entities import Flow
from domain.flow.version import FlowVersion


@dataclasses.dataclass(frozen=True, slots=True)
class FlowDraft:
    """Снапшот черновика: граф + токен оптимистической блокировки."""

    flow: Flow
    row_version: int


class FlowRepository(Protocol):
    """Хранилище сценариев: черновик + иммутабельные published-версии."""

    async def get_draft(self, flow_id: str) -> FlowDraft | None:
        """Возвращает редактируемый черновик сценария со своим row_version."""
        ...

    async def save_draft(self, flow: Flow, *, expected_row_version: int | None) -> int:
        """Сохраняет черновик; возвращает новый row_version.

        ``expected_row_version=None`` означает «только создать новый черновик»;
        если черновик уже существует — ConcurrencyError (слепая перезапись
        запрещена).

        :raises application.errors.ConcurrencyError: черновик изменён
            конкурентно или уже существует при попытке создания.
        """
        ...

    async def publish(
        self,
        flow_id: str,
        *,
        expected_row_version: int,
        bot_id: str | None = None,
        actor_id: str | None = None,
    ) -> FlowVersion:
        """Замораживает провалидированный черновик в иммутабельную версию.

        Сверяет ``expected_row_version`` с текущим черновиком (анти-TOCTOU:
        публикуется ровно тот снапшот, что прошёл BR-001/BR-006). Повторная
        публикация неизменённого черновика идемпотентна: возвращается уже
        существующая версия с тем же content_hash (безопасный ретрай после
        сбоя закрепления версии за ботом).

        :raises application.errors.ConcurrencyError: черновик изменён после
            валидации.
        """
        ...

    async def get_version(self, flow_version_id: str) -> FlowVersion | None:
        """Иммутабельный снапшот (для рантайма и активных Session)."""
        ...

    async def list_versions(self, flow_id: str) -> list[FlowVersion]:
        """История версий сценария (для UI и отката)."""
        ...
