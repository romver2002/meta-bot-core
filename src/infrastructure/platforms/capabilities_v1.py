"""Матрица возможностей v1 — общая для Telegram и MAX.

Ровно те блоки, что реализованы Flow Engine (BR-006 отсекает остальное при
публикации). http_request/custom_code добавятся со своими этапами; источник
различий платформ — platform-reference.md + ADR-0005.
"""

from __future__ import annotations

from domain.capabilities import CapabilityMatrix
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType

ENGINE_V1_CAPABILITIES = CapabilityMatrix(
    node_types=frozenset(
        {
            NodeType.SEND_MESSAGE,
            NodeType.SHOW_BUTTONS,
            NodeType.ASK,
            NodeType.CONDITION,
            NodeType.SAVE,
            NodeType.OPEN_MINI_APP,
            NodeType.HTTP_REQUEST,
        }
    ),
    trigger_types=frozenset(
        {
            TriggerType.START,
            TriggerType.TEXT,
            TriggerType.CALLBACK,
            TriggerType.MINI_APP_RESULT,
        }
    ),
    button_actions=frozenset({ButtonAction.NEXT, ButtonAction.CALLBACK, ButtonAction.URL, ButtonAction.OPEN_MINI_APP}),
)
