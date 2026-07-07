"""Безопасный вычислитель условий блока condition.

Никакого ``eval``: выражение приходит от автора бота (недоверенный ввод).
Поддерживается ровно одна форма: ``операнд ОПЕРАТОР операнд`` либо имя
переменной (истинность). Операнд — имя переменной, число, 'строка' или
true/false. Недостающая переменная и несравнимые типы дают False —
сценарий уходит в ветку "нет", а не падает.
"""

from __future__ import annotations

from collections.abc import Mapping

_OPERATORS = ("==", "!=", ">=", "<=", ">", "<")
_MISSING = object()
_MIN_QUOTED_LENGTH = 2  # минимум две кавычки: '' или ""


def evaluate_condition(expression: str, variables: Mapping[str, object]) -> bool:
    expr = expression.strip()
    if not expr:
        return False
    for operator in _OPERATORS:
        if operator in expr:
            left_raw, right_raw = expr.split(operator, 1)
            left = _resolve(left_raw.strip(), variables)
            right = _resolve(right_raw.strip(), variables)
            return _compare(operator, left, right)
    return bool(_resolve(expr, variables) not in (_MISSING, None, "", False, 0))


def _resolve(token: str, variables: Mapping[str, object]) -> object:
    if len(token) >= _MIN_QUOTED_LENGTH and token[0] == token[-1] and token[0] in {"'", '"'}:
        return token[1:-1]
    lowered = token.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return variables.get(token, _MISSING)


def _compare(operator: str, left: object, right: object) -> bool:
    if left is _MISSING or right is _MISSING:
        # Неизвестная переменная: равенство недоказуемо, неравенство — тривиально истинно.
        return operator == "!="
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return _ordered(operator, float(left), float(right))
    if isinstance(left, str) and isinstance(right, str):
        return _ordered(operator, left, right)
    return False


def _ordered(operator: str, left: float | str, right: float | str) -> bool:
    # mypy: обе ветки гомогенны по типам, сравнение корректно.
    if operator == ">=":
        return left >= right  # type: ignore[operator]
    if operator == "<=":
        return left <= right  # type: ignore[operator]
    if operator == ">":
        return left > right  # type: ignore[operator]
    return left < right  # type: ignore[operator]
