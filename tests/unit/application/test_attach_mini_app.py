"""AttachMiniAppUseCase (BR-003) на фейках."""

import pytest

from application.errors import BotNotFoundError
from application.use_cases.attach_mini_app import AttachMiniAppUseCase
from domain.errors import MiniAppInvariantError
from tests.unit.application.fakes import InMemoryBotRepository
from tests.unit.factories import make_bot

pytestmark = pytest.mark.unit


async def _use_case() -> tuple[AttachMiniAppUseCase, InMemoryBotRepository]:
    bots = InMemoryBotRepository()
    await bots.save(make_bot("bot-1"))
    return AttachMiniAppUseCase(bots=bots), bots


async def test_attach_https_mini_app() -> None:
    use_case, bots = await _use_case()
    bot = await use_case.execute("bot-1", "https://shop.example.com", title="Витрина")
    assert bot.mini_app is not None
    assert bot.mini_app.url == "https://shop.example.com"
    assert bots.storage["bot-1"].mini_app is not None


async def test_attach_rejects_non_https() -> None:
    use_case, _ = await _use_case()
    with pytest.raises(MiniAppInvariantError):
        await use_case.execute("bot-1", "http://insecure.example.com")


async def test_attach_unknown_bot() -> None:
    use_case, _ = await _use_case()
    with pytest.raises(BotNotFoundError):
        await use_case.execute("ghost", "https://x.example.com")
