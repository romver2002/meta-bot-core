"""BR-002: Bot заводится только по уже выданному платформой токену."""

import pytest

from application.errors import BotCreationError
from application.use_cases.create_bot import CreateBotUseCase
from domain.bot.value_objects import BotStatus, Platform
from tests.unit.application.fakes import InMemoryBotRepository, InMemoryTokenVault

pytestmark = pytest.mark.unit


async def test_create_bot_stores_secret_only_in_vault_br002() -> None:
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    use_case = CreateBotUseCase(bots=bots, token_vault=vault)

    bot = await use_case.execute(
        name="Кофейня Bot",
        platform=Platform.MAX,
        token_secret="fake-token-not-a-real-secret",
    )

    assert bot.status is BotStatus.DRAFT
    assert bots.storage[bot.id] is bot
    # Секрет ушёл в vault, на агрегате — только ссылка.
    assert vault.secrets[bot.token.vault_ref] == "fake-token-not-a-real-secret"
    # Секрет не светится в repr агрегата (маскированный Token.__repr__).
    assert "fake-token-not-a-real-secret" not in repr(bot)


async def test_create_bot_rejects_empty_token_br002() -> None:
    use_case = CreateBotUseCase(bots=InMemoryBotRepository(), token_vault=InMemoryTokenVault())
    with pytest.raises(BotCreationError, match="BR-002"):
        await use_case.execute(name="Без токена", platform=Platform.TELEGRAM, token_secret="   ")
