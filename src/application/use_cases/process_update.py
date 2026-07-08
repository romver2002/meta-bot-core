"""ProcessUpdateUseCase — ядро Flow Engine.

Принимает платформонезависимый ``IncomingEvent`` (нормализован адаптером в
webhook-роуте), находит бота и его опубликованную версию сценария, ведёт
``Session`` (FSM) и исполняет цепочку блоков до точки ожидания.

Правила маршрутизации события:
1. callback: сначала кнопки текущего узла (action=next), затем callback-триггеры;
2. text при ожидающей сессии (блок ask) — потребляется как ответ;
3. mini_app_result при сессии на узле open_mini_app — результат mini app,
   продолжаем сценарий; иначе — matching mini_app_result-триггеров;
4. иначе — матчинг входных триггеров; нераспознанное событие игнорируется.

Поддерживаемые блоки v1: send_message, show_buttons, ask, condition, save,
open_mini_app. Остальные типы отклоняются при публикации CapabilityMatrix
адаптеров (BR-006); здесь — защита в глубину через FlowExecutionError.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Awaitable, Callable

from application.errors import BotNotFoundError, FlowExecutionError, FlowNotFoundError
from application.ports.bot_platform import PlatformFactory, SendMessageCommand
from application.ports.bot_repository import BotRepository
from application.ports.flow_repository import FlowRepository
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

_Send = Callable[[str, tuple[Button, ...]], Awaitable[None]]


@dataclasses.dataclass(frozen=True, slots=True)
class _Route:
    """Событие распознано; ``start_node_id=None`` — цепочка уже завершена."""

    start_node_id: str | None


class ProcessUpdateUseCase:
    """Исполняет один входящий update от платформы."""

    def __init__(
        self,
        bots: BotRepository,
        flows: FlowRepository,
        sessions: SessionRepository,
        token_vault: TokenVaultPort,
        platform_factory: PlatformFactory,
    ) -> None:
        self._bots = bots
        self._flows = flows
        self._sessions = sessions
        self._token_vault = token_vault
        self._platform_factory = platform_factory

    async def execute(self, event: IncomingEvent) -> None:
        bot = await self._bots.get(event.bot_id)
        if bot is None:
            raise BotNotFoundError(f"Бот {event.bot_id!r} не найден")
        if bot.status is not BotStatus.PUBLISHED or bot.published_flow_version_id is None:
            return  # пауза/черновик: бот не отвечает
        if event.platform is not bot.platform:
            return  # защита от чужого вебхука

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

        platform = self._platform_factory.for_platform(bot.platform)
        token = await self._token_vault.retrieve(bot.token.vault_ref)

        async def send(text: str, buttons: tuple[Button, ...] = ()) -> None:
            await platform.send_message(
                SendMessageCommand(
                    bot_token=token,
                    external_chat_id=event.external_chat_id,
                    text=text,
                    buttons=buttons,
                )
            )

        route = self._route(flow, session, event)
        if route is None:
            return  # нераспознанное событие — сценарий не трогаем

        chain_ended = await self._run_chain(flow, route.start_node_id, session, send, mini_app_url)
        if chain_ended:
            # Сценарий дошёл до конца: пара (Bot, user) свободна, следующий
            # триггер начнёт новую сессию на актуальной версии (ADR-0008).
            session.complete()
        await self._sessions.save(session)

    # ── маршрутизация события ────────────────────────────────────────────────

    def _route(self, flow: Flow, session: Session, event: IncomingEvent) -> _Route | None:
        if event.event_type is TriggerType.CALLBACK:
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
            return trigger
        return None

    # ── исполнение цепочки блоков ────────────────────────────────────────────

    async def _run_chain(
        self,
        flow: Flow,
        start_node_id: str | None,
        session: Session,
        send: _Send,
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
                await send(render_text(str(node.params.get("prompt", "")), session.variables), ())
                session.await_answer(str(node.params.get("save_as", "")))
                return False  # ждём ответ пользователя
            elif node.type is NodeType.OPEN_MINI_APP:
                if mini_app_url is None:
                    raise FlowExecutionError(f"Боту не привязан mini app для блока {node.id!r}")
                label = str(node.params.get("button_text", "")) or "Открыть"
                await send(
                    render_text(str(node.params.get("text", "")), session.variables),
                    (Button(label=label, action=ButtonAction.OPEN_MINI_APP, target=mini_app_url),),
                )
                return False  # ждём результат mini app (mini_app_result)
            elif node.type is NodeType.CONDITION:
                outcome = evaluate_condition(str(node.params.get("expression", "")), session.variables)
                node_id = self._transition_target(flow, node.id, "true" if outcome else "false")
            elif node.type is NodeType.SAVE:
                session.remember(
                    str(node.params.get("key", "")),
                    render_text(str(node.params.get("value", "")), session.variables),
                )
                node_id = self._transition_target(flow, node.id, "next")
            else:
                raise FlowExecutionError(f"Блок {node.type} ещё не поддерживается движком (отклоняется BR-006)")
        raise FlowExecutionError(f"Превышен лимит {MAX_STEPS} шагов — вероятен цикл в сценарии {flow.id!r}")

    @staticmethod
    def _transition_target(flow: Flow, node_id: str | None, outcome: str) -> str | None:
        if node_id is None:
            return None
        for transition in flow.transitions:
            if transition.source_node_id == node_id and transition.on == outcome:
                return transition.target_node_id
        return None
