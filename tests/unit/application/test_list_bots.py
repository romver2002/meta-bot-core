"""ListBotsUseCase: реестр ботов конструктора («Мои боты»)."""

from __future__ import annotations

import pytest

from application.use_cases.list_bots import ListBotsUseCase
from domain.bot.entities import Bot
from domain.bot.value_objects import Platform, Token
from tests.unit.application.fakes import InMemoryBotRepository

pytestmark = pytest.mark.unit


def _bot(bot_id: str, name: str, platform: Platform = Platform.TELEGRAM) -> Bot:
    return Bot(id=bot_id, name=name, platform=platform, token=Token(vault_ref=f"vault:{bot_id}"))


async def test_empty_installation_returns_empty_list() -> None:
    use_case = ListBotsUseCase(bots=InMemoryBotRepository())
    assert await use_case.execute() == []


async def test_returns_all_bots_newest_first() -> None:
    bots = InMemoryBotRepository()
    first = _bot("a" * 32, "Первый")
    second = _bot("b" * 32, "Второй", Platform.MAX)
    await bots.save(first)
    await bots.save(second)

    result = await ListBotsUseCase(bots=bots).execute()

    assert [bot.id for bot in result] == [second.id, first.id]
