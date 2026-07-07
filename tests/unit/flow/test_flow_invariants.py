"""Структурная целостность графа Flow (инварианты domain-model.md)."""

import pytest

from domain.errors import ButtonInvariantError, FlowIntegrityError
from domain.flow.entities import Button, Flow, Node, Transition, Trigger
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType

pytestmark = pytest.mark.unit


def _node(node_id: str) -> Node:
    return Node(id=node_id, type=NodeType.SEND_MESSAGE, params={"text": "…"})


def test_transition_to_missing_node_rejected() -> None:
    with pytest.raises(FlowIntegrityError, match="несуществующий"):
        Flow(
            id="f",
            name="битый",
            nodes={"a": _node("a")},
            transitions=(Transition(source_node_id="a", target_node_id="ghost"),),
        )


def test_trigger_to_missing_node_rejected() -> None:
    with pytest.raises(FlowIntegrityError, match="несуществующий"):
        Flow(
            id="f",
            name="битый",
            nodes={"a": _node("a")},
            triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="ghost"),),
        )


def test_node_key_must_match_node_id() -> None:
    with pytest.raises(FlowIntegrityError, match="не совпадает"):
        Flow(id="f", name="битый", nodes={"wrong-key": _node("a")})


def test_next_button_to_missing_node_rejected() -> None:
    node = Node(
        id="menu",
        type=NodeType.SHOW_BUTTONS,
        params={"text": "Куда?"},
        buttons=(Button(label="Дальше", action=ButtonAction.NEXT, target="ghost"),),
    )
    with pytest.raises(FlowIntegrityError, match="несуществующий"):
        Flow(id="f", name="битый", nodes={"menu": node})


def test_url_button_requires_https() -> None:
    with pytest.raises(ButtonInvariantError, match="HTTPS"):
        Button(label="Сайт", action=ButtonAction.URL, target="http://example.com")


def test_button_requires_label() -> None:
    with pytest.raises(ButtonInvariantError, match="подпись"):
        Button(label="  ", action=ButtonAction.NEXT, target="a")
