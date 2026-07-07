"""BR-001: публикация бота — только валидный токен + непустой Flow с триггером.

Плюс жизненный цикл Draft -> Published -> Paused -> Published и
неизменяемость платформы (memory-bank/domain/domain-model.md).
"""

import pytest

from domain.bot.value_objects import BotStatus, Platform
from domain.errors import BotInvariantError, BotLifecycleError, BotPublicationError
from domain.flow.entities import Flow
from tests.unit.factories import make_bot, make_flow

pytestmark = pytest.mark.unit


def test_publish_success_br001() -> None:
    bot = make_bot()
    bot.publish(flow=make_flow(), token_is_valid=True)
    assert bot.status is BotStatus.PUBLISHED


def test_publish_rejects_invalid_token_br001() -> None:
    bot = make_bot()
    with pytest.raises(BotPublicationError, match="токен"):
        bot.publish(flow=make_flow(), token_is_valid=False)
    assert bot.status is BotStatus.DRAFT


def test_publish_rejects_empty_flow_br001() -> None:
    bot = make_bot()
    empty_flow = Flow(id="flow-1", name="Пустой")
    with pytest.raises(BotPublicationError, match="пуст"):
        bot.publish(flow=empty_flow, token_is_valid=True)


def test_publish_rejects_flow_without_trigger_br001() -> None:
    bot = make_bot()
    source = make_flow()
    flow_without_triggers = Flow(
        id="flow-1",
        name="Без триггера",
        nodes=dict(source.nodes),
        transitions=source.transitions,
    )
    with pytest.raises(BotPublicationError, match="триггер"):
        bot.publish(flow=flow_without_triggers, token_is_valid=True)


def test_publish_rejects_foreign_flow_br001() -> None:
    bot = make_bot(flow_id="flow-1")
    with pytest.raises(BotPublicationError, match="не назначен"):
        bot.publish(flow=make_flow("another-flow"), token_is_valid=True)


def test_publish_rejects_bot_without_flow_br001() -> None:
    bot = make_bot(flow_id=None)
    with pytest.raises(BotPublicationError, match="не назначен"):
        bot.publish(flow=make_flow(), token_is_valid=True)


def test_lifecycle_pause_resume() -> None:
    bot = make_bot()
    bot.publish(flow=make_flow(), token_is_valid=True)
    bot.pause()
    assert bot.status is BotStatus.PAUSED
    bot.resume()
    assert bot.status is BotStatus.PUBLISHED


def test_pause_requires_published() -> None:
    with pytest.raises(BotLifecycleError):
        make_bot().pause()


def test_resume_requires_paused() -> None:
    with pytest.raises(BotLifecycleError):
        make_bot().resume()


def test_platform_is_immutable() -> None:
    bot = make_bot(platform=Platform.TELEGRAM)
    with pytest.raises(BotInvariantError, match="неизменяема"):
        bot.platform = Platform.MAX
    assert bot.platform is Platform.TELEGRAM
