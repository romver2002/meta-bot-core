"""In-memory фейки портов для unit-тестов use cases (testing-strategy.md)."""

from __future__ import annotations

from application.ports.bot_platform import SendMessageCommand
from domain.bot.entities import Bot
from domain.bot.value_objects import Platform
from domain.capabilities import CapabilityMatrix
from domain.flow.entities import Flow


class InMemoryBotRepository:
    def __init__(self) -> None:
        self.storage: dict[str, Bot] = {}

    async def get(self, bot_id: str) -> Bot | None:
        return self.storage.get(bot_id)

    async def save(self, bot: Bot) -> None:
        self.storage[bot.id] = bot


class InMemoryFlowRepository:
    def __init__(self) -> None:
        self.storage: dict[str, Flow] = {}

    async def get(self, flow_id: str) -> Flow | None:
        return self.storage.get(flow_id)

    async def save(self, flow: Flow) -> None:
        self.storage[flow.id] = flow


class InMemoryTokenVault:
    """Секреты живут только здесь; наружу уходит ссылка vault/<bot_id>."""

    def __init__(self) -> None:
        self.secrets: dict[str, str] = {}

    async def store(self, bot_id: str, secret: str) -> str:
        vault_ref = f"vault/{bot_id}"
        self.secrets[vault_ref] = secret
        return vault_ref

    async def retrieve(self, vault_ref: str) -> str:
        return self.secrets[vault_ref]


class StubPlatform:
    """Управляемый фейк BotPlatformPort."""

    def __init__(self, capabilities: CapabilityMatrix, *, token_is_valid: bool = True) -> None:
        self._capabilities = capabilities
        self._token_is_valid = token_is_valid
        self.verified_tokens: list[str] = []
        self.sent: list[SendMessageCommand] = []

    def capabilities(self) -> CapabilityMatrix:
        return self._capabilities

    async def verify_token(self, token: str) -> bool:
        self.verified_tokens.append(token)
        return self._token_is_valid

    async def send_message(self, command: SendMessageCommand) -> None:
        self.sent.append(command)


class StubPlatformFactory:
    def __init__(self, platform_port: StubPlatform) -> None:
        self._platform_port = platform_port
        self.requested: list[Platform] = []

    def for_platform(self, platform: Platform) -> StubPlatform:
        self.requested.append(platform)
        return self._platform_port
