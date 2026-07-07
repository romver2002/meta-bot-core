"""BR-003: mini app привязан к боту и живёт только по HTTPS."""

import pytest

from domain.bot.entities import MiniApp
from domain.errors import MiniAppInvariantError

pytestmark = pytest.mark.unit


def test_mini_app_created_with_https_and_bot() -> None:
    mini_app = MiniApp(id="app-1", bot_id="bot-1", url="https://shop.example.com")
    assert mini_app.url.startswith("https://")


def test_mini_app_rejects_http_url_br003() -> None:
    with pytest.raises(MiniAppInvariantError, match="HTTPS"):
        MiniApp(id="app-1", bot_id="bot-1", url="http://shop.example.com")


def test_mini_app_requires_bot_br003() -> None:
    with pytest.raises(MiniAppInvariantError, match="привязан"):
        MiniApp(id="app-1", bot_id="", url="https://shop.example.com")
