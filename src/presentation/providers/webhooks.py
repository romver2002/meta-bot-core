"""Провайдеры webhook-контура (привязка — в composition root, src/main.py)."""

from __future__ import annotations

from application.ports.bot_platform import PlatformFactory
from application.ports.idempotency import IdempotencyPort
from application.use_cases.process_update import ProcessUpdateUseCase


def get_platform_factory() -> PlatformFactory:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_idempotency() -> IdempotencyPort:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_process_update_uc() -> ProcessUpdateUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")
