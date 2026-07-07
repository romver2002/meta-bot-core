"""In-memory фейки портов для unit-тестов use cases (testing-strategy.md)."""

from __future__ import annotations

from application.errors import ConcurrencyError
from application.ports.bot_platform import SendMessageCommand
from domain.bot.entities import Bot
from domain.bot.value_objects import Platform
from domain.capabilities import CapabilityMatrix
from domain.flow.entities import Flow
from domain.flow.version import FlowVersion, FlowVersionStatus
from domain.session.entities import Session


class InMemoryBotRepository:
    def __init__(self) -> None:
        self.storage: dict[str, Bot] = {}

    async def get(self, bot_id: str) -> Bot | None:
        return self.storage.get(bot_id)

    async def save(self, bot: Bot) -> None:
        self.storage[bot.id] = bot


class InMemoryFlowRepository:
    """Версионированный фейк FlowRepository (ADR-0008): черновик + published-версии."""

    def __init__(self) -> None:
        self.drafts: dict[str, Flow] = {}
        self.row_versions: dict[str, int] = {}
        self.versions: dict[str, FlowVersion] = {}
        self._counters: dict[str, int] = {}

    async def get_draft(self, flow_id: str) -> Flow | None:
        return self.drafts.get(flow_id)

    async def save_draft(self, flow: Flow, *, expected_row_version: int | None = None) -> int:
        current = self.row_versions.get(flow.id)
        if current is None:
            self.drafts[flow.id] = flow
            self.row_versions[flow.id] = 0
            return 0
        if expected_row_version is not None and current != expected_row_version:
            raise ConcurrencyError(f"Черновик {flow.id!r} изменён конкурентно")
        self.drafts[flow.id] = flow
        self.row_versions[flow.id] = current + 1
        return self.row_versions[flow.id]

    async def publish(self, flow_id: str) -> FlowVersion:
        number = self._counters.get(flow_id, 0) + 1
        self._counters[flow_id] = number
        version = FlowVersion(
            id=f"{flow_id}:v{number}",
            flow_id=flow_id,
            status=FlowVersionStatus.PUBLISHED,
            flow=self.drafts[flow_id],
            version=number,
        )
        self.versions[version.id] = version
        return version

    async def get_version(self, flow_version_id: str) -> FlowVersion | None:
        return self.versions.get(flow_version_id)

    async def list_versions(self, flow_id: str) -> list[FlowVersion]:
        return [v for v in self.versions.values() if v.flow_id == flow_id]


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.storage: dict[tuple[str, str], Session] = {}

    async def get_active(self, bot_id: str, external_user_id: str) -> Session | None:
        return self.storage.get((bot_id, external_user_id))

    async def save(self, session: Session) -> None:
        self.storage[(session.bot_id, session.external_user_id)] = session


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
