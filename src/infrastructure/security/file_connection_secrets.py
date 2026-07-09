"""FileConnectionSecrets — dev-реализация секретов подключения.

Секреты интеграций живут в локальном JSON вне БД и вне git (`.secrets/` в
.gitignore), сгруппированы по боту и имени. Механика файла — общая
(json_file_store: атомарная запись, ошибки -> ApplicationError). Прод-хранилище
(Vault/SOPS) — тот же открытый вопрос, что и token vault; замена не трогает ядро.
"""

from __future__ import annotations

from pathlib import Path

from infrastructure.security.json_file_store import load_store, save_value


class FileConnectionSecrets:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    async def resolve(self, bot_id: str, name: str) -> str | None:
        """:raises ApplicationError: хранилище недоступно или повреждено."""
        return load_store(self._path).get(bot_id, {}).get(name)

    async def store(self, bot_id: str, name: str, value: str) -> None:
        """:raises ApplicationError: хранилище недоступно для записи."""
        save_value(self._path, bot_id, name, value)
