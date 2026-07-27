"""Матрица возможностей v1 — общая для Telegram и MAX.

Ровно те блоки, что реализованы Flow Engine (BR-006 отсекает остальное при
публикации). custom_code добавится со своим этапом; источник различий
платформ — platform-reference.md + ADR-0005.
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
            NodeType.NOTIFY,
        }
    ),
    trigger_types=frozenset(
        {
            TriggerType.START,
            TriggerType.TEXT,
            TriggerType.CALLBACK,
            TriggerType.MINI_APP_RESULT,
            # Платформонезависим: доставка идёт обычными send_message цепочки
            # (ADR-0017) — доступен и Telegram, и MAX
            TriggerType.EXTERNAL_EVENT,
        }
    ),
    button_actions=frozenset({ButtonAction.NEXT, ButtonAction.CALLBACK, ButtonAction.URL, ButtonAction.OPEN_MINI_APP}),
)
