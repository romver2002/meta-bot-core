"""Сущности агрегата Flow: сценарий как граф блоков-данных.

Node — это данные (тип + параметры), а не код (memory-bank/domain/flow-blocks.md).

Разделение проверок:
- структурная целостность (все ссылки ведут в существующие узлы) — инвариант
  агрегата, проверяется при создании;
- достижимость узлов и допустимость блоков на платформе (BR-006) — при
  валидации перед публикацией (``validate_for_publication``), потому что
  черновик в редакторе может быть временно неполным.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import Mapping

from domain.capabilities import CapabilityMatrix
from domain.errors import ButtonInvariantError, FlowIntegrityError, FlowValidationError
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType


@dataclasses.dataclass(frozen=True, slots=True)
class Button:
    """Единая модель кнопки: подпись + действие.

    В платформенное представление кнопку переводит адаптер платформы,
    не домен (memory-bank/domain/domain-model.md).
    """

    label: str
    action: ButtonAction
    target: str | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ButtonInvariantError("У кнопки должна быть подпись")
        if self.action is ButtonAction.URL:
            if not (self.target or "").startswith("https://"):
                raise ButtonInvariantError(f"Кнопка-ссылка допускает только HTTPS-URL, получено: {self.target!r}")
        elif not self.target:
            raise ButtonInvariantError(f"Действию кнопки {self.action} нужна цель (target)")


@dataclasses.dataclass(frozen=True, slots=True)
class Trigger:
    """Вход в сценарий: тип события + узел, с которого начинается исполнение."""

    id: str
    type: TriggerType
    target_node_id: str
    config: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, slots=True)
class Transition:
    """Переход между узлами графа. ``on`` — исход узла: next | true | false | …"""

    source_node_id: str
    target_node_id: str
    on: str = "next"


@dataclasses.dataclass(slots=True)
class Node:
    """Шаг сценария: данные (тип + параметры), интерпретируемые Flow Engine."""

    id: str
    type: NodeType
    params: dict[str, object] = dataclasses.field(default_factory=dict)
    buttons: tuple[Button, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise FlowIntegrityError("У узла должен быть идентификатор")


@dataclasses.dataclass(slots=True)
class Flow:
    """Корень агрегата: сценарий = граф Node + переходов + Trigger."""

    id: str
    name: str
    nodes: dict[str, Node] = dataclasses.field(default_factory=dict)
    triggers: tuple[Trigger, ...] = ()
    transitions: tuple[Transition, ...] = ()

    def __post_init__(self) -> None:
        for node_id, node in self.nodes.items():
            if node_id != node.id:
                raise FlowIntegrityError(f"Ключ узла {node_id!r} не совпадает с его идентификатором {node.id!r}")
        for transition in self.transitions:
            for endpoint in (transition.source_node_id, transition.target_node_id):
                if endpoint not in self.nodes:
                    raise FlowIntegrityError(
                        f"Переход {transition.source_node_id!r} -> "
                        f"{transition.target_node_id!r} ссылается на несуществующий узел"
                    )
        for trigger in self.triggers:
            if trigger.target_node_id not in self.nodes:
                raise FlowIntegrityError(
                    f"Триггер {trigger.id!r} ведёт в несуществующий узел {trigger.target_node_id!r}"
                )
        for node in self.nodes.values():
            for button in node.buttons:
                if button.action is ButtonAction.NEXT and button.target not in self.nodes:
                    raise FlowIntegrityError(
                        f"Кнопка {button.label!r} узла {node.id!r} ведёт в несуществующий узел {button.target!r}"
                    )

    def is_empty(self) -> bool:
        return not self.nodes

    def validate_for_publication(self, capabilities: CapabilityMatrix) -> None:
        """Проверяет сценарий перед публикацией.

        BR-006: блок/триггер/действие кнопки, недоступные на платформе бота
        по CapabilityMatrix, отклоняются. Дополнительно — достижимость всех
        узлов от триггеров (инвариант domain-model.md).

        :raises FlowValidationError: с перечнем всех найденных проблем.
        """
        problems: list[str] = [
            f"триггер {trigger.type} недоступен на платформе (BR-006)"
            for trigger in self.triggers
            if not capabilities.supports_trigger(trigger.type)
        ]
        for node in self.nodes.values():
            if not capabilities.supports_node(node.type):
                problems.append(f"блок {node.type} недоступен на платформе (BR-006)")
            problems.extend(
                f"действие кнопки {button.action} недоступно на платформе (BR-006)"
                for button in node.buttons
                if not capabilities.supports_button(button.action)
            )
        if unreachable := self._unreachable_nodes():
            problems.append("узлы недостижимы от триггеров: " + ", ".join(sorted(unreachable)))
        seen_outcomes: set[tuple[str, str]] = set()
        for transition in self.transitions:
            outcome = (transition.source_node_id, transition.on)
            if outcome in seen_outcomes:
                problems.append(
                    f"недетерминированный переход: у узла {transition.source_node_id!r} "
                    f"больше одного исхода {transition.on!r}"
                )
            seen_outcomes.add(outcome)
        if problems:
            raise FlowValidationError("; ".join(problems))

    def _unreachable_nodes(self) -> set[str]:
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in self.nodes}
        for transition in self.transitions:
            adjacency[transition.source_node_id].add(transition.target_node_id)
        for node in self.nodes.values():
            for button in node.buttons:
                if button.action is ButtonAction.NEXT and button.target is not None:
                    adjacency[node.id].add(button.target)
        queue = deque(trigger.target_node_id for trigger in self.triggers)
        visited: set[str] = set()
        while queue:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            queue.extend(adjacency[node_id] - visited)
        return set(self.nodes) - visited
