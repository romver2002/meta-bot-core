"""Подстановка переменных сценария в текст блока: ``{имя}`` -> значение.

Сознательно НЕ ``str.format``: только простые плейсхолдеры-идентификаторы,
без format-spec и вложенных выражений — шаблон приходит от автора бота
(недоверенный ввод). Отсутствующая переменная подставляется пустой строкой.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_text(template: str, variables: Mapping[str, object]) -> str:
    return _PLACEHOLDER.sub(lambda match: str(variables.get(match.group(1), "")), template)
