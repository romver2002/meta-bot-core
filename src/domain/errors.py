"""Доменные ошибки meta-bot-core.

Каждая ошибка соответствует нарушению инварианта из
memory-bank/domain/domain-model.md или бизнес-правила BR-* из
memory-bank/domain/business-rules.md.
"""


class DomainError(Exception):
    """Базовая ошибка домена."""


class BotInvariantError(DomainError):
    """Нарушен инвариант агрегата Bot (например, смена платформы после создания)."""


class BotLifecycleError(DomainError):
    """Недопустимый переход статуса бота (Draft -> Published -> Paused)."""


class BotPublicationError(DomainError):
    """Нарушено условие публикации бота (BR-001)."""


class MiniAppInvariantError(DomainError):
    """Нарушен инвариант mini app: HTTPS-URL, привязка к боту (BR-003)."""


class FlowIntegrityError(DomainError):
    """Нарушена структурная целостность графа сценария (висячие ссылки)."""


class FlowValidationError(DomainError):
    """Сценарий не проходит валидацию перед публикацией (BR-006, достижимость)."""


class ButtonInvariantError(DomainError):
    """Нарушен инвариант кнопки (подпись, цель действия, HTTPS для url)."""


class SessionStateError(DomainError):
    """Недопустимая операция над FSM-состоянием сессии."""
