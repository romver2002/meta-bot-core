"""Порты «секретов подключения» — ключей внешних API за блоком http_request.

Отдельно от bot-token (TokenVaultPort): это ЛЮБОЙ секрет интеграции (ключ
OpenRouter, токен CRM…), привязанный к боту по имени. В определение Flow
секрет НЕ попадает — узел ссылается на него как ``{{secret:имя}}``, значение
подставляется на лету (architecture/security.md).
"""

from __future__ import annotations

from typing import Protocol


class SecretResolverPort(Protocol):
    """Чтение секрета подключения (для движка при сборке http_request)."""

    async def resolve(self, bot_id: str, name: str) -> str | None: ...


class ConnectionSecretWriterPort(Protocol):
    """Запись секрета подключения (для Admin API)."""

    async def store(self, bot_id: str, name: str, value: str) -> None: ...
