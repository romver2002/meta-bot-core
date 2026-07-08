"""SetConnectionSecretUseCase на фейках."""

import pytest

from application.errors import BotNotFoundError
from application.use_cases.set_connection_secret import SetConnectionSecretUseCase
from tests.unit.application.fakes import InMemoryBotRepository
from tests.unit.factories import make_bot


class _WriterSpy:
    def __init__(self) -> None:
        self.stored: dict[tuple[str, str], str] = {}

    async def store(self, bot_id: str, name: str, value: str) -> None:
        self.stored[(bot_id, name)] = value


pytestmark = pytest.mark.unit


async def test_stores_secret_for_existing_bot() -> None:
    bots, writer = InMemoryBotRepository(), _WriterSpy()
    await bots.save(make_bot("bot-1"))
    use_case = SetConnectionSecretUseCase(bots=bots, secrets=writer)

    await use_case.execute("bot-1", "openrouter", "sk-secret-value")

    assert writer.stored[("bot-1", "openrouter")] == "sk-secret-value"


async def test_unknown_bot_raises_and_nothing_stored() -> None:
    bots, writer = InMemoryBotRepository(), _WriterSpy()
    use_case = SetConnectionSecretUseCase(bots=bots, secrets=writer)

    with pytest.raises(BotNotFoundError):
        await use_case.execute("ghost", "openrouter", "sk")
    assert writer.stored == {}
