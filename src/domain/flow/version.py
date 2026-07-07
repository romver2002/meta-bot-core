"""FlowVersion — снапшот сценария (ADR-0008).

Черновик правится in-place; публикация замораживает его в иммутабельную
published-версию. Рантайм исполняет закреплённую версию
(``Bot.published_flow_version_id``), активная ``Session`` доигрывает свою
(``Session.flow_version_id``) — публикация не трогает исполняемое.
"""

from __future__ import annotations

import dataclasses
import enum

from domain.flow.entities import Flow


class FlowVersionStatus(enum.StrEnum):
    """Статус версии сценария."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclasses.dataclass(frozen=True, slots=True)
class FlowVersion:
    """Иммутабельный снапшот графа сценария.

    ``version`` — монотонный номер published-версии; у черновика он ``None``.
    """

    id: str
    flow_id: str
    status: FlowVersionStatus
    flow: Flow
    version: int | None = None
