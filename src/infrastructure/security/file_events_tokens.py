"""File-хранилище events-токенов (dev; ADR-0017).

Отдельный файл от connections.json сознательно: секреты подключений движок
резолвит в ``{{secret:*}}`` блока http_request, а events-токен — вход
аутентификации POST /events и в интерполяцию не попадает никогда (BR-010).
"""

from __future__ import annotations

from pathlib import Path

from infrastructure.security.json_file_store import load_store, save_value

_KEY = "token"


class FileEventsTokens:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    async def resolve(self, bot_id: str) -> str | None:
        """:raises ApplicationError: хранилище недоступно или повреждено."""
        return load_store(self._path).get(bot_id, {}).get(_KEY)

    async def store(self, bot_id: str, token: str) -> None:
        """:raises ApplicationError: хранилище недоступно для записи."""
        save_value(self._path, bot_id, _KEY, token)
