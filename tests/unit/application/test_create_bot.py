"""BR-002: Bot заводится только по выданному токену; BR-009: connect идемпотентен."""

import pytest

from application.errors import BotCreationError
from application.use_cases.create_bot import CreateBotUseCase, token_fingerprint
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


async def test_create_bot_rejects_existing_id() -> None:
    """Create — не перезапись: коллизия id не сбрасывает работающего бота."""
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    use_case = CreateBotUseCase(bots=bots, token_vault=vault)
    first = await use_case.execute(name="Первый", platform=Platform.MAX, token_secret="fake-a")

    with pytest.raises(BotCreationError, match="уже существует"):
        await use_case.execute(name="Клон", platform=Platform.TELEGRAM, token_secret="fake-b", bot_id=first.id)
    assert bots.storage[first.id].name == "Первый"  # оригинал не тронут


async def test_create_bot_rejects_malformed_id() -> None:
    use_case = CreateBotUseCase(bots=InMemoryBotRepository(), token_vault=InMemoryTokenVault())
    with pytest.raises(BotCreationError, match="UUID"):
        await use_case.execute(name="Кривой id", platform=Platform.MAX, token_secret="fake", bot_id="bot-1")


async def test_connect_same_token_returns_existing_bot_br009() -> None:
    """BR-009: повторный connect того же токена не создаёт дубля."""
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    use_case = CreateBotUseCase(bots=bots, token_vault=vault)
    first = await use_case.execute(name="Оригинал", platform=Platform.TELEGRAM, token_secret="fake-token")

    # Тот же токен (даже с пробелами и другими name/platform) -> тот же бот.
    again = await use_case.execute(name="Клон", platform=Platform.MAX, token_secret="  fake-token  ")

    assert again.id == first.id
    assert again.name == "Оригинал"
    assert again.platform is Platform.TELEGRAM
    assert len(bots.storage) == 1
    assert first.token.fingerprint == token_fingerprint("fake-token")


async def test_connect_different_tokens_create_different_bots() -> None:
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    use_case = CreateBotUseCase(bots=bots, token_vault=vault)
    first = await use_case.execute(name="A", platform=Platform.TELEGRAM, token_secret="fake-a")
    second = await use_case.execute(name="B", platform=Platform.TELEGRAM, token_secret="fake-b")

    assert first.id != second.id
    assert len(bots.storage) == 2


async def test_connect_stores_normalized_token_in_vault() -> None:
    """Отпечаток и vault получают одно значение: токен с хвостовым переводом
    строки при копировании не должен залипнуть в vault в нерабочем виде.
    """
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    use_case = CreateBotUseCase(bots=bots, token_vault=vault)

    bot = await use_case.execute(name="Бот", platform=Platform.TELEGRAM, token_secret="  fake-token\n")

    assert vault.secrets[bot.token.vault_ref] == "fake-token"
    assert bot.token.fingerprint == token_fingerprint("fake-token")


class _RacingBotRepository(InMemoryBotRepository):
    """Симулятор гонки connect: первый save проигрывает уникальному индексу
    token_hash — победитель «успевает» появиться в хранилище.
    """

    def __init__(self, winner) -> None:
        super().__init__()
        self._winner = winner
        self._raced = False

    async def save(self, bot) -> None:
        if not self._raced:
            self._raced = True
            self.storage[self._winner.id] = self._winner
            raise BotCreationError("уникальный индекс token_hash: отпечаток уже занят")
        await super().save(bot)


async def test_connect_race_returns_winner_and_leaves_no_orphan_secret() -> None:
    """BR-009 под гонкой: проигравший возвращает победителя, vault без сирот."""
    from domain.bot.entities import Bot
    from domain.bot.value_objects import Token

    winner = Bot(
        id="a" * 32,
        name="Победитель",
        platform=Platform.TELEGRAM,
        token=Token(vault_ref="vault/winner", fingerprint=token_fingerprint("fake-token")),
    )
    bots, vault = _RacingBotRepository(winner), InMemoryTokenVault()
    use_case = CreateBotUseCase(bots=bots, token_vault=vault)

    bot = await use_case.execute(name="Проигравший", platform=Platform.TELEGRAM, token_secret="fake-token")

    assert bot.id == winner.id  # идемпотентность сохранена и под гонкой
    assert vault.secrets == {}  # компенсация: осиротевшей копии секрета нет
    assert list(bots.storage) == [winner.id]
