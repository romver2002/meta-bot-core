"""Value objects агрегата Bot (memory-bank/domain/domain-model.md)."""

from __future__ import annotations

import dataclasses
import enum


class Platform(enum.StrEnum):
    """Мессенджер бота: закрытый перечень, неизменяем после создания бота.

    Расширение перечня (VK, WhatsApp) — новое значение + новый адаптер
    за ``BotPlatformPort``; ядро при этом не меняется (ADR-0002).
    """

    TELEGRAM = "telegram"
    MAX = "max"


class BotStatus(enum.StrEnum):
    """Жизненный цикл бота: Draft -> Published -> Paused -> Published."""

    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"


@dataclasses.dataclass(frozen=True, slots=True)
class Token:
    """Ссылка на токен платформенного бота в token vault.

    Сам секрет в домене не хранится, не логируется и не попадает в БД
    в открытом виде: здесь живёт только ссылка ``vault_ref``, по которой
    infrastructure достаёт значение через ``TokenVaultPort``
    (memory-bank/architecture/security.md), и ``fingerprint`` — односторонний
    SHA-256-отпечаток секрета для идемпотентного подключения (BR-009,
    ADR-0016): по нему бот находится повторно, сам токен по отпечатку
    невосстановим. ``None`` — у ботов, подключённых до введения отпечатка.
    """

    vault_ref: str
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.vault_ref:
            raise ValueError("Token.vault_ref не может быть пустым")

    def __repr__(self) -> str:
        # Даже ссылку не светим целиком: repr агрегата попадает в логи.
        return f"Token(vault_ref='***{self.vault_ref[-4:]}')"
