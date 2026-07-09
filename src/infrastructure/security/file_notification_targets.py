"""FileNotificationTargets — dev-реализация адресатов уведомлений (ADR-0010).

Привязки «роль -> chat_id» (потенциальные ПДн) живут в локальном JSON вне БД
и вне git (`.secrets/` в .gitignore), сгруппированы по боту. Механика файла —
общая (json_file_store: атомарная запись, ошибки -> ApplicationError).
"""

from __future__ import annotations

from pathlib import Path

from infrastructure.security.json_file_store import load_store, save_value


class FileNotificationTargets:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    async def resolve(self, bot_id: str, role: str) -> str | None:
        """:raises ApplicationError: хранилище недоступно или повреждено."""
        return load_store(self._path).get(bot_id, {}).get(role)

    async def store(self, bot_id: str, role: str, chat_id: str) -> None:
        """:raises ApplicationError: хранилище недоступно для записи."""
        save_value(self._path, bot_id, role, chat_id)
