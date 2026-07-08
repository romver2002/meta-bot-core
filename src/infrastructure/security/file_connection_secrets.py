"""FileConnectionSecrets — dev-реализация секретов подключения.

Секреты интеграций живут в локальном JSON вне БД и вне git (`.secrets/` в
.gitignore), сгруппированы по боту и имени. Прод-хранилище (Vault/SOPS) — тот
же открытый вопрос, что и token vault; замена не трогает ядро и use case'ы.
"""

from __future__ import annotations

import json
from pathlib import Path


class FileConnectionSecrets:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    async def resolve(self, bot_id: str, name: str) -> str | None:
        return self._load().get(bot_id, {}).get(name)

    async def store(self, bot_id: str, name: str, value: str) -> None:
        data = self._load()
        data.setdefault(bot_id, {})[name] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        return dict(json.loads(self._path.read_text(encoding="utf-8")))
