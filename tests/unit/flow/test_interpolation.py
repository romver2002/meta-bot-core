"""Подстановка переменных сценария в текст блока."""

import pytest

from domain.flow.interpolation import render_text

pytestmark = pytest.mark.unit


def test_substitutes_known_variables() -> None:
    assert render_text("Привет, {name}!", {"name": "Роман"}) == "Привет, Роман!"


def test_missing_variable_becomes_empty() -> None:
    assert render_text("Привет, {name}!", {}) == "Привет, !"


def test_format_spec_is_not_interpreted() -> None:
    # str.format-инъекции не работают: поддерживаются только простые {имя}.
    template = "{name.__class__} {x:>100} {a[0]}"
    assert render_text(template, {"name": "y"}) == template


def test_non_string_values_are_stringified() -> None:
    assert render_text("Возраст: {age}", {"age": 18}) == "Возраст: 18"
