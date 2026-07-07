"""CapabilityMatrix — реестр возможностей платформы (данные, не код).

Различия платформ выражаются данными этой матрицы, а не ветвлением в логике
(BR-005, BR-006; ADR-0005). Конкретные матрицы заполняют платформенные
адаптеры в infrastructure и отдают через ``BotPlatformPort``; домен лишь
проверяет сценарий против матрицы (``Flow.validate_for_publication``).
"""

from __future__ import annotations

import dataclasses

from domain.flow.value_objects import ButtonAction, NodeType, TriggerType


@dataclasses.dataclass(frozen=True, slots=True)
class CapabilityMatrix:
    """Что доступно на платформе бота: блоки, триггеры, действия кнопок."""

    node_types: frozenset[NodeType]
    trigger_types: frozenset[TriggerType]
    button_actions: frozenset[ButtonAction]

    def supports_node(self, node_type: NodeType) -> bool:
        return node_type in self.node_types

    def supports_trigger(self, trigger_type: TriggerType) -> bool:
        return trigger_type in self.trigger_types

    def supports_button(self, action: ButtonAction) -> bool:
        return action in self.button_actions
