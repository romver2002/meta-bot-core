"""Общие операции с frontmatter для инструментов базы знаний.

Используется bump_frontmatter.py и mb_log.py. Работает с текстом напрямую
(без пересериализации), чтобы не трогать форматирование документов.
Только стандартная библиотека.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_DELIMITER = "---"


def load(path: Path) -> str:
    """Читает документ как UTF-8 с нормализацией переводов строк в LF.

    Нормализация делает сравнение тел и regex по frontmatter независимыми
    от CRLF/CR (иначе `.` в set_scalar съедает \\r, а git show и read_text
    дают разные переводы строк — ложные срабатывания и порча файла).
    Канонический LF в репозитории закреплён `.gitattributes`.
    """
    return normalize_newlines(path.read_bytes().decode("utf-8"))


def save(path: Path, text: str) -> None:
    """Пишет документ в UTF-8 с LF, без трансляции в os.linesep."""
    path.write_text(normalize_newlines(text), encoding="utf-8", newline="\n")


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
    """Значение скалярного поля frontmatter (без кавычек и хвостового комментария).

    Разбор согласован с валидатором (`validate_memory_bank._parse_scalar`): у
    закавыченного значения берём содержимое до закрывающей кавычки, у голого —
    отсекаем хвостовой YAML-комментарий ` #...`. Иначе `version: "3.7"  # …`
    не распознавался бы как версия и bump_minor молча сбрасывал бы её в «1.0».
    None — если поля нет.
    """
    match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm_block, re.M)
    if match is None:
        return None
    value = match.group(1).strip()
    if value and value[0] in "\"'":
        quote = value[0]
        closing = value.find(quote, 1)
        return value[1:closing] if closing != -1 else value[1:]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def set_scalar(fm_block: str, key: str, raw_value: str) -> str:
    """Заменяет строку `key: ...`; если ключа нет — добавляет перед закрывающим ---."""
    line = f"{key}: {raw_value}"
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    if pattern.search(fm_block):
        return pattern.sub(line, fm_block, count=1)
    lines = fm_block.splitlines(keepends=True)
    return "".join(lines[:-1]) + line + "\n" + lines[-1]


def parse_version(version: str | None) -> tuple[int, int] | None:
    """«1.3» → (1, 3); None — если строка не «мажор.минор»."""
    match = re.fullmatch(r"(\d+)\.(\d+)", (version or "").strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def version_increased(old: str | None, new: str | None) -> bool:
    """True — если new строго больше old по «мажор.минор».

    Если хотя бы одна версия непарсима, сравнить по числам нельзя — падаем
    на сравнение строк (`new != old`), сохраняя прежнее «отличается = поднято»
    поведение; формат такой версии всё равно поймает валидатор (MB013).
    """
    old_v, new_v = parse_version(old), parse_version(new)
    if old_v is None or new_v is None:
        return new != old
    return new_v > old_v


def bump_minor(version: str | None) -> str:
    """«1.3» → «1.4»; некорректная/отсутствующая версия нормализуется в «1.0»."""
    parsed = parse_version(version)
    if parsed is None:
        return "1.0"
    return f"{parsed[0]}.{parsed[1] + 1}"


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
