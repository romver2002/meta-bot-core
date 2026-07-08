"""Кодек Flow <-> definition (JSON-документ) — SSoT формата сценария.

Этим форматом говорят: редактор (Admin API), хранение (flow_versions.definition,
ADR-0008) и Flow Engine. Чистый домен: без фреймворков и I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from domain.flow.entities import Button, Flow, Node, Transition, Trigger
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType

DEFINITION_SCHEMA_VERSION = 1


def flow_to_definition(flow: Flow) -> dict[str, Any]:
    """Сериализует граф сценария в JSON-документ definition."""
    return {
        "doc_schema_version": DEFINITION_SCHEMA_VERSION,
        "triggers": [
            {
                "id": trigger.id,
                "type": trigger.type.value,
                "target_node_id": trigger.target_node_id,
                "config": dict(trigger.config),
            }
            for trigger in flow.triggers
        ],
        "nodes": [
            {
                "id": node.id,
                "type": node.type.value,
                "params": node.params,
                "buttons": [
                    {"label": button.label, "action": button.action.value, "target": button.target}
                    for button in node.buttons
                ],
            }
            for node in flow.nodes.values()
        ],
        "transitions": [
            {
                "source_node_id": transition.source_node_id,
                "target_node_id": transition.target_node_id,
                "on": transition.on,
            }
            for transition in flow.transitions
        ],
    }


def definition_to_flow(flow_id: str, name: str, definition: dict[str, Any]) -> Flow:
    """Восстанавливает агрегат Flow из definition (инварианты проверит конструктор)."""
    nodes = {
        raw["id"]: Node(
            id=raw["id"],
            type=NodeType(raw["type"]),
            params=dict(raw.get("params", {})),
            buttons=tuple(
                Button(label=b["label"], action=ButtonAction(b["action"]), target=b.get("target"))
                for b in raw.get("buttons", [])
            ),
        )
        for raw in definition.get("nodes", [])
    }
    triggers = tuple(
        Trigger(
            id=raw["id"],
            type=TriggerType(raw["type"]),
            target_node_id=raw["target_node_id"],
            config=dict(raw.get("config", {})),
        )
        for raw in definition.get("triggers", [])
    )
    transitions = tuple(
        Transition(
            source_node_id=raw["source_node_id"],
            target_node_id=raw["target_node_id"],
            on=raw.get("on", "next"),
        )
        for raw in definition.get("transitions", [])
    )
    return Flow(id=flow_id, name=name, nodes=nodes, triggers=triggers, transitions=transitions)


def definition_hash(definition: dict[str, Any]) -> str:
    """Каноничный sha256 документа (дедуп/идемпотентность/аудит)."""
    canonical = json.dumps(definition, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
