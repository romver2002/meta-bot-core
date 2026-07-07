"""System use-case providers (переопределяются в composition root)."""

from __future__ import annotations

from application.system.use_cases.get_healthcheck import GetHealthcheckUseCase
from application.system.use_cases.get_services_healthcheck import GetServicesHealthcheckUseCase


def get_healthcheck_uc() -> GetHealthcheckUseCase:
    """Привязывается в src/main.py (dependency_overrides)."""
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_services_healthcheck_uc() -> GetServicesHealthcheckUseCase:
    """Привязывается в src/main.py (dependency_overrides)."""
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")
