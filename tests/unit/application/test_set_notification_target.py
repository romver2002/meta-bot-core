"""SetNotificationTargetUseCase на фейках."""

import pytest

from application.errors import BotNotFoundError
from application.use_cases.set_notification_target import SetNotificationTargetUseCase
from tests.unit.application.fakes import InMemoryBotRepository, StubNotificationTargets
from tests.unit.factories import make_bot

pytestmark = pytest.mark.unit


async def test_binds_role_for_existing_bot() -> None:
    bots, targets = InMemoryBotRepository(), StubNotificationTargets()
    await bots.save(make_bot("bot-1"))
    use_case = SetNotificationTargetUseCase(bots=bots, targets=targets)

    await use_case.execute("bot-1", "admin", "chat-42")

    assert targets.stored == {("bot-1", "admin"): "chat-42"}


async def test_unknown_bot_raises_and_nothing_stored() -> None:
    bots, targets = InMemoryBotRepository(), StubNotificationTargets()
    use_case = SetNotificationTargetUseCase(bots=bots, targets=targets)

    with pytest.raises(BotNotFoundError):
        await use_case.execute("ghost", "admin", "chat-42")
    assert targets.stored == {}
