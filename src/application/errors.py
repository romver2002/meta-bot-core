"""Ошибки application-слоя (классы ошибок use cases)."""


class ApplicationError(Exception):
    """Базовая ошибка application-слоя."""


class BotNotFoundError(ApplicationError):
    """Бот с указанным идентификатором не найден."""


class FlowNotFoundError(ApplicationError):
    """Сценарий не найден или не назначен боту."""


class BotCreationError(ApplicationError):
    """Нарушена политика создания бота (BR-002: только по выданному токену)."""


class ConcurrencyError(ApplicationError):
    """Конфликт одновременного изменения (оптимистическая блокировка, ADR-0008)."""


class FlowExecutionError(ApplicationError):
    """Сбой исполнения сценария движком (неподдерживаемый блок, цикл)."""


class MiniAppAuthError(ApplicationError):
    """Init data mini app не прошла валидацию на backend (BR-007)."""


class ExternalEventAuthError(ApplicationError):
    """Внешнее событие без корректного events-токена (ADR-0017, BR-010)."""


class ExternalEventValidationError(ApplicationError):
    """Внешнее событие сформировано неверно (адресат, ключи payload)."""
