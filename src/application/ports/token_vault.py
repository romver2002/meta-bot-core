"""TokenVaultPort — порт безопасного хранилища токенов ботов.

Секрет живёт только в vault; в основной БД и логах — лишь ссылка
(``Token.vault_ref``), см. memory-bank/architecture/security.md.
"""

from __future__ import annotations

from typing import Protocol


class TokenVaultPort(Protocol):
    """Хранилище секретов: кладёт токен, возвращает ссылку; достаёт по ссылке."""

    async def store(self, bot_id: str, secret: str) -> str:
        """Сохраняет секрет и возвращает vault_ref для ``Token``."""
        ...

    async def retrieve(self, vault_ref: str) -> str:
        """Возвращает секрет по ссылке. Значение не логируется."""
        ...
