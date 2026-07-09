"""Общие помощники dev-хранилищ «bot_id -> ключ -> значение» в JSON (.secrets/).

Единая механика для секретов подключений и адресатов уведомлений (DRY):
- запись атомарна (tmp-файл + os.replace) — читатель не увидит недописанный JSON;
- ошибки I/O и формата оборачиваются в ApplicationError — контракт портов,
  который best-effort-потребители (блок notify) ловят, не роняя update.

Прод-хранилище — тот же открытый вопрос, что и token vault.
"""

from __future__ import annotations

import json
from pathlib import Path

from application.errors import ApplicationError


def load_store(path: Path) -> dict[str, dict[str, str]]:
    """Читает всё хранилище; отсутствие файла — пустое хранилище.

    :raises ApplicationError: файл недоступен или повреждён.
    """
    if not path.exists():
        return {}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise ApplicationError(f"Хранилище {path.name} недоступно или повреждено") from exc


def save_value(path: Path, bot_id: str, key: str, value: str) -> None:
    """Атомарно дописывает значение ключа бота.

    :raises ApplicationError: файл недоступен или повреждён.
    """
    data = load_store(path)
    data.setdefault(bot_id, {})[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise ApplicationError(f"Хранилище {path.name} недоступно для записи") from exc
