"""ProcessUpdateUseCase — ядро Flow Engine.

Принимает платформонезависимый ``IncomingEvent`` (нормализован адаптером в
webhook-роуте), находит бота и его опубликованную версию сценария, ведёт
``Session`` (FSM) и исполняет цепочку блоков до точки ожидания.

Правила маршрутизации события:
1. callback: сначала кнопки-варианты ответа блока ask (payload = значение),
   затем кнопки текущего узла (action=next), затем callback-триггеры;
2. text при ожидающей сессии (блок ask) — потребляется как ответ;
3. mini_app_result при сессии на узле open_mini_app — результат mini app,
   продолжаем сценарий; иначе — matching mini_app_result-триггеров;
4. иначе — матчинг входных триггеров; нераспознанное событие игнорируется.

Поддерживаемые блоки v1: send_message, show_buttons, ask, condition, save,
open_mini_app, http_request, notify. Остальные типы отклоняются при публикации
CapabilityMatrix адаптеров (BR-006); здесь — защита в глубину.
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import re
import unicodedata
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from application.errors import ApplicationError, BotNotFoundError, FlowExecutionError, FlowNotFoundError
from application.ports.bot_platform import (
    AnswerCallbackCommand,
    DeleteMessageCommand,
    EditMessageCommand,
    PlatformFactory,
    SendMessageCommand,
)
from application.ports.bot_repository import BotRepository
from application.ports.connection_secrets import SecretResolverPort
from application.ports.flow_repository import FlowRepository
from application.ports.http_client import HttpClientPort
from application.ports.notification_targets import NotificationTargetResolverPort
from application.ports.session_repository import SessionRepository
from application.ports.token_vault import TokenVaultPort
from domain.bot.value_objects import BotStatus
from domain.events import IncomingEvent
from domain.flow.conditions import evaluate_condition
from domain.flow.entities import Button, Flow, Trigger
from domain.flow.interpolation import render_text
from domain.flow.value_objects import ButtonAction, NodeType, TriggerType
from domain.session.entities import Session

MAX_STEPS = 64
_SECRET_TOKEN = re.compile(r"\{\{secret:([A-Za-z0-9_.-]+)\}\}")
logger = logging.getLogger("app.engine")

_Send = Callable[[str, tuple[Button, ...]], Awaitable[None]]
_SendTo = Callable[[str, str], Awaitable[None]]  # (external_chat_id, text) — блок notify


@dataclasses.dataclass(frozen=True, slots=True)
class _Route:
    """Событие распознано; ``start_node_id=None`` — цепочка уже завершена."""

    start_node_id: str | None


def _interpolate(value: object, variables: dict[str, object]) -> object:
    """Рекурсивно подставляет {переменные} в строковые листья тела запроса."""
    if isinstance(value, str):
        return render_text(value, variables)
    if isinstance(value, dict):
        return {key: _interpolate(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [_interpolate(item, variables) for item in value]
    return value


def _dig(payload: object, path: str) -> object:
    """Достаёт значение по dotted-пути (`choices.0.message.content`)."""
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except ValueError, IndexError:
                return None
        else:
            return None
    return current


def _flattened(variables: dict[str, object]) -> dict[str, object]:
    """Гасит спуфинг карточки уведомления пользовательским вводом.

    Переводы строк и управляющие/форматные символы в значениях переменных
    не должны дорисовывать «поля» карточки админу: перенос -> видимый « ⏎ »,
    прочие Cc/Cf-символы (bidi-переопределения и т.п.) удаляются.
    """
    return {key: _flatten(str(value)) for key, value in variables.items()}


def _flatten(value: str) -> str:
    flat = value.replace("\r\n", " ⏎ ").replace("\n", " ⏎ ").replace("\r", " ⏎ ")
    return "".join(ch for ch in flat if unicodedata.category(ch) not in {"Cc", "Cf"})


def _extract(payload: dict[str, Any], response_map: object) -> dict[str, object]:
    """Маппит поля ответа в переменные сценария по response_map."""
    result: dict[str, object] = {}
    if isinstance(response_map, dict):
        for var, path in response_map.items():
            value = _dig(payload, str(path))
            # Пишем КАЖДЫЙ ключ детерминированно: отсутствующий путь (или null
            # в ответе) -> "", иначе остаточная переменная прошлого шага «протекает»
            # в condition и пользователь видит ответ на прошлый вопрос.
            result[str(var)] = value if value is not None else ""
    return result


class ProcessUpdateUseCase:
    """Исполняет один входящий update от платформы."""

    def __init__(
        self,
        bots: BotRepository,
        flows: FlowRepository,
        sessions: SessionRepository,
        token_vault: TokenVaultPort,
        platform_factory: PlatformFactory,
        http_client: HttpClientPort,
        secrets: SecretResolverPort,
        notifications: NotificationTargetResolverPort,
    ) -> None:
        self._bots = bots
        self._flows = flows
        self._sessions = sessions
        self._token_vault = token_vault
        self._platform_factory = platform_factory
        self._http_client = http_client
        self._secrets = secrets
        self._notifications = notifications

    async def execute(self, event: IncomingEvent) -> None:
        bot = await self._bots.get(event.bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {event.bot_id!r} не найден")
        if event.platform is not bot.platform:
            return  # защита от чужого вебхука (нельзя даже подтверждать чужим адаптером)

        platform = self._platform_factory.for_platform(bot.platform)
        token = await self._token_vault.retrieve(bot.token.vault_ref)

        if event.callback_id is not None:
            # Гасим индикатор ожидания сразу и для ЛЮБОГО нажатия — в том числе
            # у бота на паузе/черновике: пауза и есть главный источник протухших
            # кнопок. Best-effort: подтверждение не важнее исполнения сценария.
            try:
                await platform.answer_callback(AnswerCallbackCommand(bot_token=token, callback_id=event.callback_id))
            except ApplicationError:
                logger.warning("Подтверждение нажатия не принято платформой", extra={"bot_id": bot.id})

        if bot.status is not BotStatus.PUBLISHED or bot.published_flow_version_id is None:
            return  # пауза/черновик: бот не отвечает (нажатие уже подтверждено выше)

        version = await self._flows.get_version(bot.published_flow_version_id)
        if version is None:
            raise FlowNotFoundError(f"Опубликованная версия {bot.published_flow_version_id!r} не найдена")
        flow = version.flow
        mini_app_url = bot.mini_app.url if bot.mini_app is not None else None

        session = await self._sessions.get_active(bot.id, event.external_user_id)
        if session is None:
            session = Session(
                id=uuid.uuid4().hex,
                bot_id=bot.id,
                external_user_id=event.external_user_id,
                flow_version_id=version.id,
            )

        # Edit-in-place (ADR-0012): первый ответ на нажатие кнопки правит само
        # сообщение с кнопкой — протухшие меню не копятся в чате. message_id
        # приходит только у callback-событий (домен events.py), чужие сообщения
        # здесь не появляются по построению.
        edit_target = event.message_id if event.event_type is TriggerType.CALLBACK else None

        async def send(text: str, buttons: tuple[Button, ...] = ()) -> None:
            nonlocal edit_target
            origin, edit_target = edit_target, None
            if origin is not None:
                try:
                    await platform.edit_message(
                        EditMessageCommand(
                            bot_token=token,
                            external_chat_id=event.external_chat_id,
                            message_id=origin,
                            text=text,
                            buttons=buttons,
                        )
                    )
                except ApplicationError:
                    pass  # платформа отказала (давность/удалено) — шлём новое сообщение
                else:
                    return
            await platform.send_message(
                SendMessageCommand(
                    bot_token=token,
                    external_chat_id=event.external_chat_id,
                    text=text,
                    buttons=buttons,
                )
            )
            if origin is not None:
                # Правка не удалась — хотя бы снимаем мёртвое меню, best-effort:
                # новое сообщение уже доставлено, недоудалённое старое не критично.
                with contextlib.suppress(ApplicationError):
                    await platform.delete_message(
                        DeleteMessageCommand(
                            bot_token=token,
                            external_chat_id=event.external_chat_id,
                            message_id=origin,
                        )
                    )

        async def send_to(chat_id: str, text: str) -> None:
            await platform.send_message(
                SendMessageCommand(bot_token=token, external_chat_id=chat_id, text=text, buttons=())
            )

        route = self._route(flow, session, event)
        if route is None:
            return  # нераспознанное событие — сценарий не трогаем

        if event.event_type is TriggerType.EXTERNAL_EVENT and event.variables:
            # Payload внешнего события → переменные сессии ДО цепочки (ADR-0017):
            # карточка рисуется обычными {подстановками}. Пишем только после
            # успешного матчинга — несматченное событие сессию не трогает.
            for key, value in event.variables.items():
                session.remember(key, value)

        chain_ended = await self._run_chain(flow, route.start_node_id, session, send, send_to, bot.id, mini_app_url)
        if chain_ended:
            # Сценарий дошёл до конца: пара (Bot, user) свободна, следующий
            # триггер начнёт новую сессию на актуальной версии (ADR-0008).
            session.complete()
        await self._sessions.save(session)

    # ── маршрутизация события ────────────────────────────────────────────────

    def _route(self, flow: Flow, session: Session, event: IncomingEvent) -> _Route | None:
        if event.event_type is TriggerType.CALLBACK:
            option = self._ask_option_answer(flow, session, event.payload)
            if option is not None:
                return option
            target = self._button_target(flow, session, event.payload)
            if target is not None:
                return _Route(target)
        elif event.event_type is TriggerType.TEXT and session.awaiting_variable is not None and event.text is not None:
            session.submit_answer(event.text)
            return _Route(self._transition_target(flow, session.current_node_id, "next"))
        elif event.event_type is TriggerType.MINI_APP_RESULT:
            node = flow.nodes.get(session.current_node_id) if session.current_node_id else None
            if node is not None and node.type is NodeType.OPEN_MINI_APP:
                session.remember(str(node.params.get("save_as", "mini_app_result")), event.payload or "")
                return _Route(self._transition_target(flow, node.id, "next"))

        trigger = self._match_trigger(flow, event)
        return _Route(trigger.target_node_id) if trigger is not None else None

    def _ask_option_answer(self, flow: Flow, session: Session, payload: str | None) -> _Route | None:
        """Кнопка-вариант блока ask: payload = готовое значение ответа.

        Быстрый ответ равноправен набранному тексту (свою «сумму» по-прежнему
        можно вбить). Чужой payload (например, «В меню» со старой карточки)
        вариантом не считается и уходит ниже — к кнопкам узла и триггерам.
        """
        if payload is None or session.awaiting_variable is None or session.current_node_id is None:
            return None
        node = flow.nodes.get(session.current_node_id)
        if node is None or node.type is not NodeType.ASK:
            return None
        for button in node.buttons:
            if button.action is ButtonAction.CALLBACK and button.target == payload:
                session.submit_answer(payload)
                return _Route(self._transition_target(flow, node.id, "next"))
        return None

    @staticmethod
    def _button_target(flow: Flow, session: Session, payload: str | None) -> str | None:
        """Кнопка action=next текущего узла: payload адаптера = id целевого узла."""
        if payload is None or session.current_node_id is None:
            return None
        node = flow.nodes.get(session.current_node_id)
        if node is None:
            return None
        for button in node.buttons:
            if button.action is ButtonAction.NEXT and button.target == payload:
                return button.target
        return None

    @staticmethod
    def _match_trigger(flow: Flow, event: IncomingEvent) -> Trigger | None:
        for trigger in flow.triggers:
            if trigger.type is not event.event_type:
                continue
            if trigger.type is TriggerType.TEXT:
                pattern = trigger.config.get("pattern")
                if pattern is not None and event.text != pattern:
                    continue
            if trigger.type is TriggerType.CALLBACK:
                payload = trigger.config.get("payload")
                if payload is not None and event.payload != payload:
                    continue
            if trigger.type is TriggerType.EXTERNAL_EVENT:
                # Имя события — в payload (ADR-0017); config["event"] не задан —
                # триггер ловит любое внешнее событие (симметрия с pattern у text)
                name = trigger.config.get("event")
                if name is not None and event.payload != name:
                    continue
            return trigger
        return None

    # ── исполнение цепочки блоков ────────────────────────────────────────────

    async def _run_chain(  # noqa: PLR0912 — диспетчер по типу блока, ветвление по своей природе
        self,
        flow: Flow,
        start_node_id: str | None,
        session: Session,
        send: _Send,
        send_to: _SendTo,
        bot_id: str,
        mini_app_url: str | None,
    ) -> bool:
        """Исполняет цепочку узлов; True — сценарий дошёл до конца (нет ожидания)."""
        node_id = start_node_id
        for _ in range(MAX_STEPS):
            if node_id is None:
                return True  # цепочка закончилась
            node = flow.nodes.get(node_id)
            if node is None:
                raise FlowExecutionError(f"Узел {node_id!r} отсутствует в сценарии {flow.id!r}")
            session.advance(node.id)

            if node.type is NodeType.SEND_MESSAGE:
                await send(render_text(str(node.params.get("text", "")), session.variables), ())
                node_id = self._transition_target(flow, node.id, "next")
            elif node.type is NodeType.SHOW_BUTTONS:
                await send(
                    render_text(str(node.params.get("text", "")), session.variables),
                    node.buttons,
                )
                return False  # ждём нажатие кнопки (callback)
            elif node.type is NodeType.ASK:
                # Кнопки узла — варианты быстрого ответа (каталог блоков);
                # свободный текст остаётся равноправным способом ответить.
                await send(render_text(str(node.params.get("prompt", "")), session.variables), node.buttons)
                session.await_answer(str(node.params.get("save_as", "")))
                return False  # ждём ответ пользователя (кнопка-вариант или текст)
            elif node.type is NodeType.OPEN_MINI_APP:
                if mini_app_url is None:
                    raise FlowExecutionError(f"Боту не привязан mini app для блока {node.id!r}")
                label = str(node.params.get("button_text", "")) or "Открыть"
                await send(
                    render_text(str(node.params.get("text", "")), session.variables),
                    (Button(label=label, action=ButtonAction.OPEN_MINI_APP, target=mini_app_url),),
                )
                return False  # ждём результат mini app (mini_app_result)
            elif node.type is NodeType.HTTP_REQUEST:
                http_outcome, extracted = await self._execute_http(node.params, session, bot_id)
                for key, value in extracted.items():
                    session.remember(key, value)
                target = self._transition_target(flow, node.id, http_outcome)
                if target is None and http_outcome != "next":
                    target = self._transition_target(flow, node.id, "next")
                node_id = target
            elif node.type is NodeType.NOTIFY:
                await self._execute_notify(node.params, session, bot_id, send_to)
                node_id = self._transition_target(flow, node.id, "next")
            elif node.type is NodeType.CONDITION:
                outcome = evaluate_condition(str(node.params.get("expression", "")), session.variables)
                node_id = self._transition_target(flow, node.id, "true" if outcome else "false")
            elif node.type is NodeType.SAVE:
                values = node.params.get("values")
                if isinstance(values, dict):
                    # Маппинг из каталога блоков: несколько переменных одним узлом
                    # (в т.ч. стирание ПДн пустыми значениями, BR-008).
                    for key, value in values.items():
                        session.remember(str(key), render_text(str(value), session.variables))
                else:
                    session.remember(
                        str(node.params.get("key", "")),
                        render_text(str(node.params.get("value", "")), session.variables),
                    )
                node_id = self._transition_target(flow, node.id, "next")
            else:
                raise FlowExecutionError(f"Блок {node.type} ещё не поддерживается движком (отклоняется BR-006)")
        if node_id is None:
            return True  # цепочка закончилась ровно на лимите — это не цикл
        raise FlowExecutionError(f"Превышен лимит {MAX_STEPS} шагов — вероятен цикл в сценарии {flow.id!r}")

    # ── notify ───────────────────────────────────────────────────────────────

    async def _execute_notify(self, params: dict[str, object], session: Session, bot_id: str, send_to: _SendTo) -> None:
        """Best-effort доставка третьему лицу (ADR-0010).

        Ничто здесь не важнее ответа пользователю: непривязанная роль, пустой
        текст, сбой резолва хранилища или доставки (ApplicationError — контракты
        портов) не прерывают цепочку. Гарантированная доставка (outbox) — вне v1.
        """
        role = params.get("to")
        text = render_text(str(params.get("text", "")), _flattened(session.variables))
        if not isinstance(role, str) or not role or not text:
            return
        try:
            chat_id = await self._notifications.resolve(bot_id, role)
            if chat_id is None:
                logger.warning("Роль уведомления не привязана — пропуск", extra={"bot_id": bot_id, "role": role})
                return
            await send_to(chat_id, text)
        except ApplicationError:
            # chat_id адресата в лог не пишем (ПДн) — роли достаточно для разбора.
            logger.warning("Уведомление роли не доставлено", extra={"bot_id": bot_id, "role": role})
            return

    # ── http_request ─────────────────────────────────────────────────────────

    async def _execute_http(
        self, params: dict[str, object], session: Session, bot_id: str
    ) -> tuple[str, dict[str, object]]:
        """Выполняет внешний HTTP-вызов; возвращает исход ('next'|'error') и переменные."""
        method = str(params.get("method", "GET")).upper()
        url = render_text(str(params.get("url", "")), session.variables)
        headers = await self._build_headers(params.get("headers"), session, bot_id)
        body = _interpolate(params.get("body"), session.variables)
        try:
            timeout = float(params.get("timeout", 10) or 10)  # type: ignore[arg-type]
        except TypeError, ValueError:
            timeout = 10.0

        response = await self._http_client.request(
            method=method, url=url, headers=headers, json_body=body, timeout=timeout
        )
        if response.status_code == 0 or response.status_code >= 400:  # noqa: PLR2004
            return "error", {}
        return "next", _extract(response.json or {}, params.get("response_map"))

    async def _build_headers(self, raw: object, session: Session, bot_id: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                rendered = render_text(str(value), session.variables)
                headers[str(key)] = await self._resolve_secrets(rendered, bot_id)
        return headers

    async def _resolve_secrets(self, value: str, bot_id: str) -> str:
        """Подставляет {{secret:имя}} значениями из хранилища секретов подключения."""
        result = value
        for match in _SECRET_TOKEN.finditer(value):
            secret = await self._secrets.resolve(bot_id, match.group(1))
            result = result.replace(match.group(0), secret or "")
        return result

    @staticmethod
    def _transition_target(flow: Flow, node_id: str | None, outcome: str) -> str | None:
        if node_id is None:
            return None
        for transition in flow.transitions:
            if transition.source_node_id == node_id and transition.on == outcome:
                return transition.target_node_id
        return None
