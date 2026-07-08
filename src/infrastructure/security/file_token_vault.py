"""FileTokenVault — dev-реализация TokenVaultPort.

Секреты живут в локальном JSON вне БД и вне git (.secrets/ в .gitignore) —
канон «токен не в основной БД» соблюдён. Прод-хранилище (Vault/SOPS/…) —
открытый вопрос ADR-0008/team; замена не трогает ни ядро, ни use case'ы.
"""

from __future__ import annotations

import json
from pathlib import Path


class FileTokenVault:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    async def store(self, bot_id: str, secret: str) -> str:
        data = self._load()
        vault_ref = f"file:{bot_id}"
        data[vault_ref] = secret
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return vault_ref

    async def retrieve(self, vault_ref: str) -> str:
        secret = self._load().get(vault_ref)
        if secret is None:
            raise KeyError(f"Секрет {vault_ref!r} не найден в token vault")
        return secret

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        return dict(json.loads(self._path.read_text(encoding="utf-8")))
