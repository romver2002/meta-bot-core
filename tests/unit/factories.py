"""Фабрики тестовых данных: валидные агрегаты по умолчанию.

Testing-strategy.md: тестовые данные — через фабрики/фикстуры; реальные
токены запрещены, только фейковые значения.
"""

from __future__ import annotations

from domain.bot.entities import Bot
from domain.bot.value_objects import Platform, Token
from domain.capabilities import CapabilityMatrix
from domain.flow.entities import Flow, Node, Transition, Trigger
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType


def full_capabilities() -> CapabilityMatrix:
    """Платформа, поддерживающая всё (удобно как базовый случай BR-006)."""
    return CapabilityMatrix(
        node_types=frozenset(NodeType),
        trigger_types=frozenset(TriggerType),
        button_actions=frozenset(ButtonAction),
    )


def make_flow(flow_id: str = "flow-1") -> Flow:
    """Минимальный валидный сценарий: /start -> приветствие -> вопрос."""
    greet = Node(id="greet", type=NodeType.SEND_MESSAGE, params={"text": "Привет, {name}!"})
    ask = Node(
        id="ask-name",
        type=NodeType.ASK,
        params={"prompt": "Как вас зовут?", "save_as": "name"},
    )
    return Flow(
        id=flow_id,
        name="Приветствие",
        nodes={node.id: node for node in (greet, ask)},
        triggers=(Trigger(id="t-start", type=TriggerType.START, target_node_id="greet"),),
        transitions=(Transition(source_node_id="greet", target_node_id="ask-name"),),
    )


def make_bot(
    bot_id: str = "bot-1",
    platform: Platform = Platform.TELEGRAM,
    flow_id: str | None = "flow-1",
) -> Bot:
    return Bot(
        id=bot_id,
        name="Тестовый бот",
        platform=platform,
        token=Token(vault_ref=f"vault/{bot_id}"),
        flow_id=flow_id,
    )
