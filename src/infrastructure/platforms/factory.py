"""PlatformFactory — выбор адаптера по value object Platform (BR-005)."""

from __future__ import annotations

from application.errors import ApplicationError
from application.ports.bot_platform import BotPlatformPort
from domain.bot.value_objects import Platform


class RegistryPlatformFactory:
    """Реестр адаптеров; наполняется в composition root (src/main.py)."""

    def __init__(self, adapters: dict[Platform, BotPlatformPort]) -> None:
        self._adapters = dict(adapters)

    def for_platform(self, platform: Platform) -> BotPlatformPort:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ApplicationError(f"Платформа {platform} не зарегистрирована в PlatformFactory")
        return adapter
