"""BotPlatformPort — порт платформы бота, и PlatformFactory — выбор адаптера.

Контракт: платформенные адаптеры (infrastructure/platforms/telegram|max)
реализуют ``BotPlatformPort``; выбор реализации по value object ``Platform``
делает ``PlatformFactory`` в composition root. Бизнес-логика по платформе
не ветвится (BR-005) — различия выражены данными ``CapabilityMatrix``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Protocol

from domain.bot.value_objects import Platform
from domain.capabilities import CapabilityMatrix
from domain.events import IncomingEvent
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


@dataclasses.dataclass(frozen=True, slots=True)
class AnswerCallbackCommand:
    """Подтверждение нажатия кнопки (гасит индикатор ожидания у пользователя).

    ``callback_id`` транзиентен — отвечать сразу; повторный ответ платформы
    трактуют идемпотентно (specs/002-platform-deep-dive, «Ответ на нажатие»).
    """

    bot_token: str
    callback_id: str


@dataclasses.dataclass(frozen=True, slots=True)
class MiniAppIdentity:
    """Доверенная личность пользователя mini app после валидации init data (BR-007)."""

    external_user_id: str
    params: Mapping[str, str]


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

    async def answer_callback(self, command: AnswerCallbackCommand) -> None:
        """Подтверждает нажатие кнопки (TG answerCallbackQuery / MAX /answers).

        :raises ApplicationError: сетевой сбой; вызывающий обязан пережить его
            best-effort — подтверждение не важнее исполнения сценария.
        """
        ...

    def parse_update(self, bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
        """Нормализует сырой update платформы в IncomingEvent (ADR-0004).

        None — событие не поддерживается конструктором (молча игнорируется).
        """
        ...

    def validate_init_data(self, token: str, init_data: str) -> MiniAppIdentity | None:
        """Валидирует init data mini app на backend (BR-007).

        None — подпись неверна или данные устарели; чистая CPU-проверка (HMAC),
        без сети. Токен и init data не логируются.
        """
        ...


class PlatformFactory(Protocol):
    """Возвращает реализацию ``BotPlatformPort`` по платформе бота (BR-005)."""

    def for_platform(self, platform: Platform) -> BotPlatformPort: ...
