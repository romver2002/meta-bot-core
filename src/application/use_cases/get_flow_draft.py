"""GetFlowDraftUseCase — чтение черновика сценария для редактора.

Read-контракт редактора: без него нельзя безопасно открыть существующий
сценарий — редактор рисковал бы перезаписать чужой черновик стартовым
шаблоном. Возвращается ровно та пара (definition, row_version), которую
клиент обязан вернуть в SaveFlowDraftUseCase (оптимистический лок, ADR-0008);
``name`` возвращать не обязательно — пустое имя при сохранении означает
«не менять», а не «сбросить на имя бота».
"""

from __future__ import annotations

import dataclasses
from typing import Any

from application.errors import BotNotFoundError, FlowNotFoundError
from application.ports.bot_repository import BotRepository
from application.ports.flow_repository import FlowRepository
from domain.flow.codec import flow_to_definition


@dataclasses.dataclass(frozen=True, slots=True)
class FlowDraftView:
    """Черновик глазами редактора: канонический definition + токен конкуренции."""

    flow_id: str
    name: str
    definition: dict[str, Any]
    row_version: int


class GetFlowDraftUseCase:
    """Отдаёт черновик сценария бота (канонический контракт domain/flow/codec.py).

    :raises BotNotFoundError: бот не найден.
    :raises FlowNotFoundError: у бота ещё нет черновика (редактор начинает
        с чистого листа, а не перезаписывает вслепую).
    """

    def __init__(self, bots: BotRepository, flows: FlowRepository) -> None:
        self._bots = bots
        self._flows = flows

    async def execute(self, bot_id: str) -> FlowDraftView:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")
        if bot.flow_id is None:
            raise FlowNotFoundError(f"У бота {bot_id!r} ещё нет черновика сценария")
        draft = await self._flows.get_draft(bot.flow_id)
        if draft is None:
            raise FlowNotFoundError(f"Черновик сценария {bot.flow_id!r} не найден")
        return FlowDraftView(
            flow_id=draft.flow.id,
            name=draft.flow.name,
            definition=flow_to_definition(draft.flow),
            row_version=draft.row_version,
        )
