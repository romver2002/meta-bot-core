"""SubmitExternalEventUseCase — внешнее событие «система → сценарий» (ADR-0017, BR-010).

Вход «система → сценарий»: CRM-уведомления, внешние агрегаторы, напоминания
планировщиков. Обобщает прецедент SubmitMiniAppResult:
HTTP-вход → IncomingEvent → движок; v1 адресует только личные чаты, где
идентичность пользователя и адрес доставки — одно и то же лицо
(домен: ``domain/addressing.py``).
"""

from __future__ import annotations

import asyncio
import contextlib
import enum
import hmac
import logging
import re

from application.errors import (
    BotNotFoundError,
    ExternalEventAuthError,
    ExternalEventValidationError,
)
from application.ports.bot_repository import BotRepository
from application.ports.events_token import EventsTokenResolverPort
from application.ports.idempotency import IdempotencyPort, Reservation
from application.ports.notification_targets import NotificationTargetResolverPort
from application.use_cases.process_update import ProcessUpdateUseCase, UpdateOutcome
from domain.addressing import address_identity
from domain.events import IncomingEvent
from domain.flow.value_objects import TriggerType

# Те же правила, что имена переменных {подстановок} (domain/flow/interpolation.py)
_VARIABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_MAX_KEYS = 64
_MAX_VALUE_LEN = 4000  # текст сообщения MAX ≤ 4000 — длиннее в карточку не влезет
# Треть дефолтного EVENTS_INFLIGHT_TTL: composition root задаёт значение от
# фактического TTL, инвариант — heartbeat < TTL (ops/configuration.md).
_DEFAULT_HEARTBEAT_SECONDS = 40.0

logger = logging.getLogger("app.events")


class ExternalEventOutcome(enum.StrEnum):
    """Исход приёма события — контракт ответа вызывающему (ADR-0019).

    Вызывающий по нему решает: считать доставленным, повторить позже или
    звать человека. «Не исполнено» никогда не выдаётся за доставку.
    """

    DELIVERED = "delivered"  # сценарий исполнил событие
    DUPLICATE = "duplicate"  # этот event_id уже был исполнен
    IN_FLIGHT = "in_flight"  # событие с этим event_id обрабатывается — повторить позже
    BOT_NOT_PUBLISHED = "bot_not_published"  # бот на паузе/черновике — повторить позже
    NO_TRIGGER_MATCHED = "no_trigger_matched"  # в сценарии нет триггера под это событие


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
        *,
        lease_heartbeat_seconds: float = _DEFAULT_HEARTBEAT_SECONDS,
    ) -> None:
        self._bots = bots
        self._events_tokens = events_tokens
        self._targets = targets
        self._idempotency = idempotency
        self._process_update = process_update
        self._lease_heartbeat = lease_heartbeat_seconds

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
    ) -> ExternalEventOutcome:
        """Возвращает честный исход: исполнено / дубль / в работе / не исполнено."""
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
                raise ExternalEventValidationError(
                    f"Роль {role!r} не привязана к чату (PUT /bots/{{id}}/notifications/{role})"
                )

        idempotency_key = f"events:{bot_id}:{event_id}" if event_id is not None else None
        if idempotency_key is not None:
            # Ключ берётся коротким «в работе» и продлевается только фактическим
            # исполнением (ADR-0019): падение ядра посреди отправки не должно
            # сжигать event_id на сутки, иначе карточка теряется навсегда.
            reservation = await self._idempotency.reserve(idempotency_key)
            if reservation is Reservation.DONE:
                return ExternalEventOutcome.DUPLICATE
            if reservation is Reservation.IN_FLIGHT:
                return ExternalEventOutcome.IN_FLIGHT

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
            outcome = await self._execute_under_lease(idempotency_key, incoming)
        except BaseException:
            # Доставка не состоялась — освобождаем ключ, иначе ретрай вызывающего
            # с тем же event_id молча ляжет в «дубликаты» (живой прогон
            # 2026-07-26: 500 от платформы сжёг event_id). BaseException, а не
            # Exception: отмена задачи (разрыв соединения, shutdown) — не Exception.
            await self._release(idempotency_key)
            raise

        if outcome is UpdateOutcome.EXECUTED:
            await self._confirm(idempotency_key)
            return ExternalEventOutcome.DELIVERED

        # Сценарий событие не исполнил — ключ не сжигаем: повтор должен пройти,
        # когда бота снимут с паузы или вернут триггер в опубликованный сценарий.
        await self._release(idempotency_key)
        logger.warning("Внешнее событие не исполнено сценарием", extra={"bot_id": bot_id, "outcome": str(outcome)})
        if outcome is UpdateOutcome.BOT_NOT_PUBLISHED:
            return ExternalEventOutcome.BOT_NOT_PUBLISHED
        # FOREIGN_PLATFORM здесь недостижим: событие собрано с bot.platform.
        return ExternalEventOutcome.NO_TRIGGER_MATCHED

    async def _execute_under_lease(self, key: str | None, event: IncomingEvent) -> UpdateOutcome:
        """Исполняет событие, продлевая аренду ключа, пока цепочка жива.

        Исполнение сверху не ограничено (MAX_STEPS шагов, таймаут ``http_request``
        задаёт автор сценария), а TTL «в работе» короткий — без продления ключ
        истекает под живой работой, и ретрай вызывающего доставляет карточку
        второй раз (ADR-0019).
        """
        if key is None:
            return await self._process_update.execute(event)
        heartbeat = asyncio.create_task(self._renew_lease(key))
        try:
            return await self._process_update.execute(event)
        finally:
            # Дожидаемся отмены до confirm: иначе продление могло бы сбить
            # уже проставленный полный TTL обратно на короткий.
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    async def _renew_lease(self, key: str) -> None:
        while True:
            await asyncio.sleep(self._lease_heartbeat)
            with contextlib.suppress(Exception):
                await self._idempotency.touch(key)

    async def _confirm(self, key: str | None) -> None:
        """Продлевает ключ best-effort: бухгалтерия дедупа не имеет права отменить
        уже состоявшуюся доставку — иначе вызывающий получит ошибку, повторит
        событие и получатель увидит карточку дважды.
        """
        if key is None:
            return
        try:
            await asyncio.shield(self._idempotency.confirm(key))
        except Exception:  # noqa: BLE001 — любой сбой хранилища дедупа, доставка уже состоялась
            logger.warning("Ключ event_id не продлён — возможен повторный приём", extra={"key": key})

    async def _release(self, key: str | None) -> None:
        """Освобождает ключ best-effort: под отменой задачи shield доводит
        удаление до конца, а сбой Redis не подменяет исходную ошибку.
        """
        if key is None:
            return
        with contextlib.suppress(Exception):
            await asyncio.shield(self._idempotency.forget(key))

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
