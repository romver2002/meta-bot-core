"""AuthenticateMiniAppUseCase (BR-007) на фейках."""

import pytest

from application.errors import BotNotFoundError, MiniAppAuthError
from application.ports.bot_platform import MiniAppIdentity
from application.use_cases.authenticate_mini_app import AuthenticateMiniAppUseCase
from tests.unit.application.fakes import (
    InMemoryBotRepository,
    InMemoryTokenVault,
    StubPlatform,
    StubPlatformFactory,
)
from tests.unit.factories import full_capabilities, make_bot

pytestmark = pytest.mark.unit


async def _use_case(validator):
    bots, vault = InMemoryBotRepository(), InMemoryTokenVault()
    bot = make_bot("bot-1")
    bot.token = type(bot.token)(vault_ref=await vault.store("bot-1", "fake-token"))
    await bots.save(bot)
    platform = StubPlatform(full_capabilities(), init_data_validator=validator)
    return AuthenticateMiniAppUseCase(
        bots=bots, token_vault=vault, platform_factory=StubPlatformFactory(platform)
    ), platform


async def test_authenticates_with_bot_token_from_vault() -> None:
    seen: list[str] = []

    def validator(token: str, init_data: str) -> MiniAppIdentity | None:
        seen.append(token)
        return MiniAppIdentity(external_user_id="777", params={"user": init_data})

    use_case, _ = await _use_case(validator)
    identity = await use_case.execute("bot-1", "raw-init-data")

    assert identity.external_user_id == "777"
    assert seen == ["fake-token"]  # токен взят из vault, не из запроса


async def test_invalid_init_data_raises() -> None:
    use_case, _ = await _use_case(lambda _t, _d: None)
    with pytest.raises(MiniAppAuthError, match="BR-007"):
        await use_case.execute("bot-1", "bad")


async def test_unknown_bot_raises() -> None:
    use_case, _ = await _use_case(lambda _t, _d: None)
    with pytest.raises(BotNotFoundError):
        await use_case.execute("ghost", "x")
