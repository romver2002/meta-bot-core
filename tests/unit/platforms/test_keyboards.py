"""Маппинг доменных кнопок в клавиатуры платформ (включая open_mini_app)."""

import pytest

from domain.flow.entities import Button
from domain.flow.value_objects import ButtonAction
from infrastructure.platforms.max.adapter import _keyboard_attachment
from infrastructure.platforms.telegram.adapter import _keyboard

pytestmark = pytest.mark.unit


def _btn(action: ButtonAction, target: str) -> Button:
    return Button(label="B", action=action, target=target)


def test_telegram_maps_open_mini_app_to_web_app() -> None:
    kb = _keyboard((_btn(ButtonAction.OPEN_MINI_APP, "https://shop.example.com"),))
    assert kb == {"inline_keyboard": [[{"text": "B", "web_app": {"url": "https://shop.example.com"}}]]}


def test_telegram_maps_url_and_callback() -> None:
    kb = _keyboard((_btn(ButtonAction.URL, "https://x.example"), _btn(ButtonAction.NEXT, "node1")))
    assert kb is not None
    assert kb["inline_keyboard"][0][0] == {"text": "B", "url": "https://x.example"}
    assert kb["inline_keyboard"][1][0] == {"text": "B", "callback_data": "node1"}


def test_max_maps_open_mini_app_to_open_app() -> None:
    att = _keyboard_attachment((_btn(ButtonAction.OPEN_MINI_APP, "https://shop.example.com"),))
    assert att is not None
    assert att["type"] == "inline_keyboard"
    assert att["payload"]["buttons"][0][0] == {
        "type": "open_app",
        "text": "B",
        "web_app": {"url": "https://shop.example.com"},
    }


def test_empty_keyboard_is_none() -> None:
    assert _keyboard(()) is None
    assert _keyboard_attachment(()) is None
