"""Безопасный вычислитель условий блока condition (без eval)."""

import pytest

from domain.flow.conditions import evaluate_condition

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("expression", "variables", "expected"),
    [
        ("name == 'Роман'", {"name": "Роман"}, True),
        ("name == 'Роман'", {"name": "Иван"}, False),
        ("name != 'Роман'", {"name": "Иван"}, True),
        ("age >= 18", {"age": 18}, True),
        ("age >= 18", {"age": 17}, False),
        ("age < 100", {"age": 42}, True),
        ("score > 4.5", {"score": 4.9}, True),
        ("vip == true", {"vip": True}, True),
        ("vip == false", {"vip": True}, False),
        ("city == 'Москва'", {}, False),  # неизвестная переменная — ветка «нет»
        ("city != 'Москва'", {}, True),
        ("name", {"name": "Роман"}, True),  # истинность переменной
        ("name", {"name": ""}, False),
        ("name", {}, False),
        ("", {"x": 1}, False),
        ("age >= 'много'", {"age": 18}, False),  # несравнимые типы — «нет», не падение
    ],
)
def test_evaluate_condition(expression: str, variables: dict[str, object], expected: bool) -> None:
    assert evaluate_condition(expression, variables) is expected


def test_no_code_execution_paths() -> None:
    """Выражение — данные: попытки кода дают безопасный False, а не исполнение."""
    assert evaluate_condition("__import__('os').system('id')", {}) is False
    assert evaluate_condition("1 if True else 0", {}) is False
