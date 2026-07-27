"""In-memory фейки портов для unit-тестов use cases (testing-strategy.md)."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from application.errors import ApplicationError, ConcurrencyError
from application.ports.bot_platform import (
    AnswerCallbackCommand,
    DeleteMessageCommand,
    EditMessageCommand,
    MiniAppIdentity,
    RegisterWebhookCommand,
    SendMessageCommand,
)
from application.ports.flow_repository import FlowDraft
from application.ports.http_client import HttpResponse
from domain.bot.entities import Bot
from domain.bot.value_objects import Platform
from domain.capabilities import CapabilityMatrix
from domain.events import IncomingEvent
from domain.flow.entities import Flow
from domain.flow.version import FlowVersion, FlowVersionStatus
from domain.session.entities import Session, SessionStatus


class InMemoryBotRepository:
    def __init__(self) -> None:
        self.storage: dict[str, Bot] = {}

    async def get(self, bot_id: str) -> Bot | None:
        return self.storage.get(bot_id)

    async def find_by_token_fingerprint(self, fingerprint: str) -> Bot | None:
        return next(
            (bot for bot in self.storage.values() if bot.token.fingerprint == fingerprint),
            None,
        )

    async def save(self, bot: Bot) -> None:
        self.storage[bot.id] = bot

    async def list_all(self) -> list[Bot]:
        # Контракт порта: новые первыми (в фейке — обратный порядок вставки).
        return list(reversed(self.storage.values()))


class InMemoryFlowRepository:
    """Версионированный фейк FlowRepository (ADR-0008): черновик + published-версии."""

    def __init__(self) -> None:
        self.drafts: dict[str, Flow] = {}
        self.row_versions: dict[str, int] = {}
        self.versions: dict[str, FlowVersion] = {}
        self._counters: dict[str, int] = {}

    async def get_draft(self, flow_id: str) -> FlowDraft | None:
        flow = self.drafts.get(flow_id)
        if flow is None:
            return None
        return FlowDraft(flow=flow, row_version=self.row_versions[flow_id])

    async def save_draft(self, flow: Flow, *, expected_row_version: int | None) -> int:
        current = self.row_versions.get(flow.id)
        if current is None:
            if expected_row_version is not None:
                raise ConcurrencyError(f"Черновика {flow.id!r} не существует")
            self.drafts[flow.id] = flow
            self.row_versions[flow.id] = 0
            return 0
        if expected_row_version is None or current != expected_row_version:
            raise ConcurrencyError(f"Черновик {flow.id!r} изменён конкурентно")
        self.drafts[flow.id] = flow
        self.row_versions[flow.id] = current + 1
        return self.row_versions[flow.id]

    async def publish(
        self,
        flow_id: str,
        *,
        expected_row_version: int,
        bot_id: str | None = None,
        actor_id: str | None = None,
    ) -> FlowVersion:
        if self.row_versions.get(flow_id) != expected_row_version:
            raise ConcurrencyError(f"Черновик {flow_id!r} изменён после валидации")
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
        session = self.storage.get((bot_id, external_user_id))
        if session is None or session.status is not SessionStatus.ACTIVE:
            return None
        return session

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

    async def delete(self, vault_ref: str) -> None:
        self.secrets.pop(vault_ref, None)


class StubPlatform:
    """Управляемый фейк BotPlatformPort."""

    def __init__(
        self,
        capabilities: CapabilityMatrix,
        *,
        token_is_valid: bool = True,
        parser: Callable[[str, Mapping[str, object]], IncomingEvent | None] | None = None,
        init_data_validator: Callable[[str, str], MiniAppIdentity | None] | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._token_is_valid = token_is_valid
        self._parser = parser
        self._init_data_validator = init_data_validator
        self.verified_tokens: list[str] = []
        self.sent: list[SendMessageCommand] = []
        self.answered: list[AnswerCallbackCommand] = []
        self.edited: list[EditMessageCommand] = []
        self.deleted: list[DeleteMessageCommand] = []
        self.registered: list[RegisterWebhookCommand] = []
        self.edit_fails = False  # инъекция отказа платформы (лимит давности и т.п.)
        self.delete_fails = False
        self.verify_token_error: Exception | None = None  # сеть/TLS до платформы упали
        self.register_webhook_error: Exception | None = None  # платформа отклонила подписку

    def capabilities(self) -> CapabilityMatrix:
        return self._capabilities

    def parse_update(self, bot_id: str, payload: Mapping[str, object]) -> IncomingEvent | None:
        return self._parser(bot_id, payload) if self._parser is not None else None

    def validate_init_data(self, token: str, init_data: str) -> MiniAppIdentity | None:
        return self._init_data_validator(token, init_data) if self._init_data_validator else None

    async def verify_token(self, token: str) -> bool:
        self.verified_tokens.append(token)
        if self.verify_token_error is not None:
            raise self.verify_token_error
        return self._token_is_valid

    async def register_webhook(self, command: RegisterWebhookCommand) -> None:
        if self.register_webhook_error is not None:
            raise self.register_webhook_error
        self.registered.append(command)

    async def send_message(self, command: SendMessageCommand) -> None:
        self.sent.append(command)

    async def edit_message(self, command: EditMessageCommand) -> None:
        if self.edit_fails:
            raise ApplicationError("платформа отказала в правке")
        self.edited.append(command)

    async def delete_message(self, command: DeleteMessageCommand) -> None:
        if self.delete_fails:
            raise ApplicationError("платформа отказала в удалении")
        self.deleted.append(command)

    async def answer_callback(self, command: AnswerCallbackCommand) -> None:
        self.answered.append(command)


class StubIdempotency:
    """In-memory реализация IdempotencyPort."""

    def __init__(self) -> None:
        self.seen: set[str] = set()

    async def first_time(self, key: str) -> bool:
        if key in self.seen:
            return False
        self.seen.add(key)
        return True

    async def forget(self, key: str) -> None:
        self.seen.discard(key)


class StubPlatformFactory:
    def __init__(self, platform_port: StubPlatform) -> None:
        self._platform_port = platform_port
        self.requested: list[Platform] = []

    def for_platform(self, platform: Platform) -> StubPlatform:
        self.requested.append(platform)
        return self._platform_port


class StubHttpClient:
    """Управляемый фейк HttpClientPort: возвращает заданный ответ, пишет вызовы."""

    def __init__(self, response: HttpResponse | None = None) -> None:
        self.response = response or HttpResponse(status_code=200, json={}, text="")
        self.calls: list[dict[str, object]] = []

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        json_body: object | None,
        timeout: float,
    ) -> HttpResponse:
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "json_body": json_body})
        return self.response


class StubSecretResolver:
    """In-memory SecretResolverPort (секреты подключения по имени)."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = secrets or {}

    async def resolve(self, bot_id: str, name: str) -> str | None:
        return self._secrets.get(name)


class StubNotificationTargets:
    """In-memory резолвер и writer адресатов уведомлений.

    ``defaults`` — привязки «роль -> chat_id» для любого бота (удобство тестов);
    ``store`` пишет изолированно по боту, как реальное хранилище.
    """

    def __init__(self, targets: dict[str, str] | None = None) -> None:
        self.defaults = targets or {}
        self.stored: dict[tuple[str, str], str] = {}

    async def resolve(self, bot_id: str, role: str) -> str | None:
        return self.stored.get((bot_id, role), self.defaults.get(role))

    async def store(self, bot_id: str, role: str, chat_id: str) -> None:
        self.stored[(bot_id, role)] = chat_id
