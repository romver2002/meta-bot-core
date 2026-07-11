"""GetFlowDraftUseCase: read-контракт черновика для редактора."""

from __future__ import annotations

import pytest

from application.errors import BotNotFoundError, FlowNotFoundError
from application.use_cases.get_flow_draft import GetFlowDraftUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from domain.flow.codec import flow_to_definition
from tests.unit.application.fakes import InMemoryBotRepository, InMemoryFlowRepository
from tests.unit.factories import make_bot, make_flow

pytestmark = pytest.mark.unit


async def test_returns_canonical_definition_and_row_version() -> None:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    await bots.save(make_bot("bot-1"))
    definition = flow_to_definition(make_flow("editor-flow"))
    saved = await SaveFlowDraftUseCase(bots, flows).execute(
        "bot-1", definition, expected_row_version=None
    )

    draft = await GetFlowDraftUseCase(bots, flows).execute("bot-1")

    # Пара (definition, row_version) — ровно та, что нужна безопасному save:
    # раундтрип через кодек не искажает сценарий (SSoT формата).
    assert draft.definition == definition
    assert draft.row_version == saved.row_version
    assert draft.flow_id == saved.flow_id
    assert draft.name  # имя черновика отдаётся редактору (bot.name по умолчанию)


async def test_row_version_follows_saves() -> None:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    await bots.save(make_bot("bot-1"))
    definition = flow_to_definition(make_flow("editor-flow"))
    save = SaveFlowDraftUseCase(bots, flows)
    await save.execute("bot-1", definition, expected_row_version=None)
    await save.execute("bot-1", definition, expected_row_version=0)

    draft = await GetFlowDraftUseCase(bots, flows).execute("bot-1")

    assert draft.row_version == 1  # токен конкуренции актуален после второго save


async def test_bot_without_draft_raises_flow_not_found() -> None:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    await bots.save(make_bot("bot-1", flow_id=None))  # черновик ещё не создавался

    with pytest.raises(FlowNotFoundError, match="нет черновика"):
        await GetFlowDraftUseCase(bots, flows).execute("bot-1")


async def test_dangling_flow_reference_raises_flow_not_found() -> None:
    # flow_id привязан, но черновика в хранилище нет (например, вычищен) —
    # редактору отвечаем 404, а не отдаём пустоту.
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()
    await bots.save(make_bot("bot-1"))  # фабрика привязывает flow-1 без черновика

    with pytest.raises(FlowNotFoundError, match="не найден"):
        await GetFlowDraftUseCase(bots, flows).execute("bot-1")


async def test_unknown_bot_raises_bot_not_found() -> None:
    bots, flows = InMemoryBotRepository(), InMemoryFlowRepository()

    with pytest.raises(BotNotFoundError):
        await GetFlowDraftUseCase(bots, flows).execute("ghost")
