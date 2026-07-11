"""SaveFlowDraftUseCase — сохранение черновика сценария из редактора."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

from application.errors import BotNotFoundError
from application.ports.bot_repository import BotRepository
from application.ports.flow_repository import FlowRepository
from domain.flow.codec import definition_to_flow


@dataclasses.dataclass(frozen=True, slots=True)
class SavedDraft:
    flow_id: str
    row_version: int


class SaveFlowDraftUseCase:
    """Принимает definition (контракт domain/flow/codec.py) и сохраняет черновик.

    Инварианты графа проверяет конструктор Flow (битые ссылки отклоняются);
    конкуренция — оптимистическим локом (``expected_row_version`` из прошлого
    ответа; None — только создание нового черновика). Первый сохранённый
    черновик привязывает Flow к боту (Bot 1—1 Flow).

    :raises BotNotFoundError: бот не найден.
    :raises domain.errors.FlowIntegrityError: definition с битыми ссылками.
    :raises application.errors.ConcurrencyError: конкурентное изменение.
    """

    def __init__(self, bots: BotRepository, flows: FlowRepository) -> None:
        self._bots = bots
        self._flows = flows

    async def execute(
        self,
        bot_id: str,
        definition: dict[str, Any],
        *,
        expected_row_version: int | None,
        name: str = "",
    ) -> SavedDraft:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")

        flow_id = bot.flow_id or uuid.uuid4().hex
        if not name:
            # Пустое имя = «не менять»: сохранение по read-контракту (definition +
            # row_version, ADR-0008) не должно молча сбрасывать имя сценария на bot.name.
            existing = await self._flows.get_draft(flow_id) if bot.flow_id else None
            name = existing.flow.name if existing is not None else bot.name
        flow = definition_to_flow(flow_id, name, definition)
        row_version = await self._flows.save_draft(flow, expected_row_version=expected_row_version)

        if bot.flow_id is None:
            bot.assign_flow(flow_id)
            await self._bots.save(bot)
        return SavedDraft(flow_id=flow_id, row_version=row_version)
