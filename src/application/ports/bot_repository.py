"""BotRepository — порт хранилища агрегата Bot.

Примечание: канонический список портов в overview.md этот порт не включает
(перечислены FlowRepository/SessionRepository/…), однако CreateBotUseCase и
PublishBotUseCase требуют персистенции Bot. Расхождение зафиксировано в
memory-bank/current/progress.md; после ратификации порт вносится в
patterns.md/glossary.md.
"""

from __future__ import annotations

from typing import Protocol

from domain.bot.entities import Bot


class BotRepository(Protocol):
    """Хранилище агрегата Bot. Граница агрегата = граница транзакции."""

    async def get(self, bot_id: str) -> Bot | None: ...

    async def find_by_token_fingerprint(self, fingerprint: str) -> Bot | None:
        """Бот по SHA-256-отпечатку токена — идемпотентный connect (BR-009)."""
        ...

    async def save(self, bot: Bot) -> None: ...

    async def list_all(self) -> list[Bot]:
        """Все боты инсталляции, новые первыми (порядок создания, DESC)."""
        ...
