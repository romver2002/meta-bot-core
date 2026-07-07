"""BotPlatformPort — порт платформы бота, и PlatformFactory — выбор адаптера.

Контракт: платформенные адаптеры (infrastructure/platforms/telegram|max)
реализуют ``BotPlatformPort``; выбор реализации по value object ``Platform``
делает ``PlatformFactory`` в composition root. Бизнес-логика по платформе
не ветвится (BR-005) — различия выражены данными ``CapabilityMatrix``.
"""

from __future__ import annotations

import dataclasses
from typing import Protocol

from domain.bot.value_objects import Platform
from domain.capabilities import CapabilityMatrix
from domain.flow.entities import Button


@dataclasses.dataclass(frozen=True, slots=True)
class SendMessageCommand:
    """Платформонезависимая команда отправки сообщения.

    Кнопки передаются доменной моделью ``Button``; в платформенное
    представление их переводит адаптер (inline-клавиатура Telegram,
    кнопки MAX), не application.
    """

    bot_token: str
    external_chat_id: str
    text: str
    buttons: tuple[Button, ...] = ()


class BotPlatformPort(Protocol):
    """Порт мессенджера: всё, что ядру нужно от платформы бота."""

    def capabilities(self) -> CapabilityMatrix:
        """Матрица возможностей платформы (данные для BR-006)."""
        ...

    async def verify_token(self, token: str) -> bool:
        """Проверяет токен у платформы (условие публикации, BR-001)."""
        ...

    async def send_message(self, command: SendMessageCommand) -> None:
        """Отправляет сообщение пользователю от имени бота.

        :raises ApplicationError: реализация оборачивает сетевые сбои
            в свои ошибки; доменных ошибок здесь не бывает.
        """
        ...


class PlatformFactory(Protocol):
    """Возвращает реализацию ``BotPlatformPort`` по платформе бота (BR-005)."""

    def for_platform(self, platform: Platform) -> BotPlatformPort: ...
