"""SubmitExternalEventUseCase — внешнее событие «система → сценарий» (ADR-0017, BR-010).

Вход «система → сценарий»: CRM-уведомления, внешние агрегаторы, напоминания
планировщиков. Обобщает прецедент SubmitMiniAppResult:
HTTP-вход → IncomingEvent → движок; v1 адресует только личные чаты, где
идентичность пользователя и адрес доставки — одно и то же лицо
(домен: ``domain/addressing.py``).
"""

from __future__ import annotations

import hmac
import re

from application.errors import (
    BotNotFoundError,
    ExternalEventAuthError,
    ExternalEventValidationError,
)
from application.ports.bot_repository import BotRepository
from application.ports.events_token import EventsTokenResolverPort
from application.ports.idempotency import IdempotencyPort
from application.ports.notification_targets import NotificationTargetResolverPort
from application.use_cases.process_update import ProcessUpdateUseCase
from domain.addressing import address_identity
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType

# Те же правила, что имена переменных {подстановок} (domain/flow/interpolation.py)
_VARIABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_MAX_KEYS = 64
_MAX_VALUE_LEN = 4000  # текст сообщения MAX ≤ 4000 — длиннее в карточку не влезет


class SubmitExternalEventUseCase:
    """Аутентифицирует событие bot-scoped токеном, резолвит адресата и подаёт
    его в движок как ``external_event``.

    :raises ExternalEventAuthError: токен не задан или не совпал (401).
    :raises BotNotFoundError: бот не найден (404).
    :raises ExternalEventValidationError: адресат/payload некорректны (422).
    """

    def __init__(
        self,
        bots: BotRepository,
        events_tokens: EventsTokenResolverPort,
        targets: NotificationTargetResolverPort,
        idempotency: IdempotencyPort,
        process_update: ProcessUpdateUseCase,
    ) -> None:
        self._bots = bots
        self._events_tokens = events_tokens
        self._targets = targets
        self._idempotency = idempotency
        self._process_update = process_update

    async def execute(
        self,
        bot_id: str,
        *,
        provided_token: str,
        event: str,
        role: str | None,
        chat_id: str | None,
        payload: dict[str, str],
        event_id: str | None,
    ) -> bool:
        """True — событие подано в движок; False — дубль по ``event_id``."""
        # Токен проверяется ДО чтения бота: без валидного токена эндпоинт не
        # раскрывает даже существование bot_id (404 получает только владелец токена).
        expected = await self._events_tokens.resolve(bot_id)
        if expected is None or not hmac.compare_digest(expected.encode(), provided_token.encode()):
            raise ExternalEventAuthError("Неверный или не заданный events-токен (X-Events-Token)")

        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {bot_id!r} не найден")

        self._validate_payload(payload)
        if (role is None) == (chat_id is None):
            raise ExternalEventValidationError("Адресат: укажи ровно одно из role / chat_id")
        if role is not None:
            chat_id = await self._targets.resolve(bot_id, role)
            if chat_id is None:
                raise ExternalEventValidationError(f"Роль {role!r} не привязана к чату (PUT /bots/{{id}}/notifications/{role})")

        idempotency_key = f"events:{bot_id}:{event_id}" if event_id is not None else None
        if idempotency_key is not None and not await self._idempotency.first_time(idempotency_key):
            return False  # дубль ретрая вызывающего — событие уже доставлялось

        incoming = IncomingEvent(
            platform=bot.platform,
            bot_id=bot.id,
            # v1: только личный чат — идентичность и адрес доставки совпадают
            # по значению (ADR-0017, как в SubmitMiniAppResultUseCase), но не
            # по написанию: адрес может быть в форме конвенции `user:<id>`,
            # а вебхук отдаёт id без префикса. Ключ сессии — идентичность,
            # иначе нажатие кнопки на карточке попадёт в ДРУГУЮ сессию.
            external_user_id=address_identity(chat_id or ""),
            external_chat_id=chat_id or "",
            event_type=TriggerType.EXTERNAL_EVENT,
            payload=event,
            variables=dict(payload),
        )
        try:
            await self._process_update.execute(incoming)
        except Exception:
            # Доставка не состоялась — освобождаем ключ, иначе ретрай
            # вызывающего с тем же event_id молча ляжет в «дубликаты»
            # (живой прогон 2026-07-26: 500 от платформы сжёг event_id).
            if idempotency_key is not None:
                await self._idempotency.forget(idempotency_key)
            raise
        return True

    @staticmethod
    def _validate_payload(payload: dict[str, str]) -> None:
        if len(payload) > _MAX_KEYS:
            raise ExternalEventValidationError(f"Payload: не больше {_MAX_KEYS} ключей")
        for key, value in payload.items():
            if not _VARIABLE_NAME.fullmatch(key):
                raise ExternalEventValidationError(
                    f"Ключ payload {key!r} не годится в имя переменной ({{подстановку}})"
                )
            if len(value) > _MAX_VALUE_LEN:
                raise ExternalEventValidationError(f"Значение {key!r} длиннее {_MAX_VALUE_LEN} символов")
