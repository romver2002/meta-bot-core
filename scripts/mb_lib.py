"""Общие операции с frontmatter для инструментов базы знаний.

Используется bump_frontmatter.py и mb_log.py. Работает с текстом напрямую
(без пересериализации), чтобы не трогать форматирование документов.
Только стандартная библиотека.
"""
from __future__ import annotations

import re
from datetime import date

_DELIMITER = "---"


def split_document(text: str) -> tuple[str | None, str]:
    """Разделяет документ на (блок frontmatter с разделителями, тело).

    Если frontmatter отсутствует или не закрыт — возвращает (None, text):
    такие документы инструменты не трогают, о дефекте сообщит валидатор (MB010/MB011).
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _DELIMITER:
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIMITER:
            return "".join(lines[: i + 1]), "".join(lines[i + 1:])
    return None, text


def get_scalar(fm_block: str, key: str) -> str | None:
    """Значение скалярного поля frontmatter (без кавычек); None, если поля нет."""
    match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm_block, re.M)
    if match is None:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] in "\"'" and value.endswith(value[0]):
        value = value[1:-1]
    return value


def set_scalar(fm_block: str, key: str, raw_value: str) -> str:
    """Заменяет строку `key: ...`; если ключа нет — добавляет перед закрывающим ---."""
    line = f"{key}: {raw_value}"
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    if pattern.search(fm_block):
        return pattern.sub(line, fm_block, count=1)
    lines = fm_block.splitlines(keepends=True)
    return "".join(lines[:-1]) + line + "\n" + lines[-1]


def bump_minor(version: str | None) -> str:
    """«1.3» → «1.4»; некорректная/отсутствующая версия нормализуется в «1.0»."""
    match = re.fullmatch(r"(\d+)\.(\d+)", version or "")
    if match is None:
        return "1.0"
    return f"{match.group(1)}.{int(match.group(2)) + 1}"


def touch(text: str, today: date) -> str | None:
    """Поднимает version (минор +1) и ставит updated=today.

    None — если frontmatter отсутствует/не закрыт (документ не изменяется).
    """
    fm_block, body = split_document(text)
    if fm_block is None:
        return None
    fm_block = set_scalar(fm_block, "version", f'"{bump_minor(get_scalar(fm_block, "version"))}"')
    fm_block = set_scalar(fm_block, "updated", today.isoformat())
    return fm_block + body
