"""Сущности агрегата Bot.

Bot — корень агрегата: конструктор управляет поведением уже
зарегистрированного платформенного бота по токену, а не создаёт его аккаунт
(BR-002). Ссылки на Flow/Session — только по идентификатору
(memory-bank/domain/domain-model.md).
"""

from __future__ import annotations

import dataclasses

from domain.bot.value_objects import BotStatus, Platform, Token
from domain.errors import (
    BotInvariantError,
    BotLifecycleError,
    BotPublicationError,
    MiniAppInvariantError,
)
from domain.flow.entities import Flow


@dataclasses.dataclass(frozen=True, slots=True)
class MiniApp:
    """Web-приложение, привязанное к боту.

    BR-003: mini app не существует вне чат-бота (в MAX — обязательное
    условие платформы); URL — только HTTPS. Init data валидируется на
    backend до доверия пользователю (BR-007, реализация — в
    infrastructure/platforms/*/mini_app_auth.py).
    """

    id: str
    bot_id: str
    url: str
    title: str = ""

    def __post_init__(self) -> None:
        if not self.bot_id:
            raise MiniAppInvariantError("MiniApp обязан быть привязан к боту (BR-003)")
        if not self.url.startswith("https://"):
            raise MiniAppInvariantError(f"URL mini app — только HTTPS (BR-003): {self.url!r}")


@dataclasses.dataclass(slots=True)
class Bot:
    """Корень агрегата: платформа + токен (ссылка в vault) + ссылка на сценарий."""

    id: str
    name: str
    platform: Platform
    token: Token
    flow_id: str | None = None
    status: BotStatus = BotStatus.DRAFT
    mini_app: MiniApp | None = None

    def __setattr__(self, name: str, value: object) -> None:
        # Инвариант domain-model.md: Platform неизменяема после создания бота.
        if name == "platform" and hasattr(self, "platform"):
            raise BotInvariantError("Платформа бота неизменяема после создания")
        super().__setattr__(name, value)

    def assign_flow(self, flow_id: str) -> None:
        self.flow_id = flow_id

    def publish(self, flow: Flow, *, token_is_valid: bool) -> None:
        """Публикует бота.

        BR-001: публикация возможна только при валидном токене
        зарегистрированного платформенного бота и непустом Flow с хотя бы
        одним Trigger. Валидность токена устанавливает use case через
        платформенный порт и передаёт сюда готовым фактом — домен не ходит
        в сеть.

        :raises BotPublicationError: нарушено условие публикации (BR-001).
        """
        if not token_is_valid:
            raise BotPublicationError("BR-001: токен не подтверждён платформой — публикация невозможна")
        if self.flow_id is None or flow.id != self.flow_id:
            raise BotPublicationError("BR-001: боту не назначен переданный сценарий")
        if flow.is_empty():
            raise BotPublicationError("BR-001: сценарий пуст — публикация невозможна")
        if not flow.triggers:
            raise BotPublicationError("BR-001: у сценария нет ни одного триггера")
        self.status = BotStatus.PUBLISHED

    def pause(self) -> None:
        if self.status is not BotStatus.PUBLISHED:
            raise BotLifecycleError(f"Приостановить можно только опубликованного бота: {self.status}")
        self.status = BotStatus.PAUSED

    def resume(self) -> None:
        if self.status is not BotStatus.PAUSED:
            raise BotLifecycleError(f"Возобновить можно только приостановленного бота: {self.status}")
        self.status = BotStatus.PUBLISHED
