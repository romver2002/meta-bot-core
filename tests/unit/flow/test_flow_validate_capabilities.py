"""BR-006: Flow.validate_for_publication по CapabilityMatrix платформы."""

import pytest

from domain.capabilities import CapabilityMatrix
from domain.errors import FlowValidationError
from domain.flow.entities import Flow, Node, Trigger
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType
from tests.unit.factories import full_capabilities, make_flow

pytestmark = pytest.mark.unit


def test_valid_flow_passes_full_capabilities_br006() -> None:
    make_flow().validate_for_publication(full_capabilities())


def test_unsupported_node_type_rejected_br006() -> None:
    capabilities = CapabilityMatrix(
        node_types=frozenset(NodeType) - {NodeType.ASK},
        trigger_types=frozenset(TriggerType),
        button_actions=frozenset(ButtonAction),
    )
    with pytest.raises(FlowValidationError, match=r"ask.*BR-006"):
        make_flow().validate_for_publication(capabilities)


def test_unsupported_trigger_rejected_br006() -> None:
    capabilities = CapabilityMatrix(
        node_types=frozenset(NodeType),
        trigger_types=frozenset(TriggerType) - {TriggerType.START},
        button_actions=frozenset(ButtonAction),
    )
    with pytest.raises(FlowValidationError, match=r"триггер.*BR-006"):
        make_flow().validate_for_publication(capabilities)


def test_unreachable_node_rejected() -> None:
    flow = make_flow()
    orphan = Node(id="orphan", type=NodeType.SEND_MESSAGE, params={"text": "до меня не дойти"})
    flow_with_orphan = Flow(
        id=flow.id,
        name=flow.name,
        nodes={**flow.nodes, "orphan": orphan},
        triggers=flow.triggers,
        transitions=flow.transitions,
    )
    with pytest.raises(FlowValidationError, match=r"недостижимы.*orphan"):
        flow_with_orphan.validate_for_publication(full_capabilities())


def test_flow_without_trigger_marks_all_unreachable() -> None:
    flow = Flow(
        id="f",
        name="без входа",
        nodes={"a": Node(id="a", type=NodeType.SEND_MESSAGE)},
        triggers=(),
    )
    with pytest.raises(FlowValidationError, match="недостижимы"):
        flow.validate_for_publication(full_capabilities())


def test_reachability_via_next_button() -> None:
    from domain.flow.entities import Button

    menu = Node(
        id="menu",
        type=NodeType.SHOW_BUTTONS,
        params={"text": "Куда?"},
        buttons=(Button(label="Дальше", action=ButtonAction.NEXT, target="finish"),),
    )
    finish = Node(id="finish", type=NodeType.SEND_MESSAGE, params={"text": "Готово"})
    flow = Flow(
        id="f",
        name="кнопочный",
        nodes={"menu": menu, "finish": finish},
        triggers=(Trigger(id="t", type=TriggerType.START, target_node_id="menu"),),
    )
    flow.validate_for_publication(full_capabilities())
