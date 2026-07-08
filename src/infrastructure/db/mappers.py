"""Мапперы домен ↔ хранение (ADR-0008).

Домен не наследует ORM-Base: перевод выполняется здесь, на границе.
Формат definition — доменный кодек (domain/flow/codec.py, SSoT).
Идентификаторы агрегатов в Pg-репозиториях — UUID (use case генерирует
``uuid4().hex``); внутренние id узлов/триггеров живут в JSONB как строки.
"""

from __future__ import annotations

import uuid

from domain.bot.entities import Bot, MiniApp
from domain.bot.value_objects import Token
from domain.flow.codec import definition_to_flow
from domain.flow.version import FlowVersion, FlowVersionStatus
from domain.session.entities import Session
from infrastructure.db.models import BotModel, FlowVersionModel, MiniAppModel, SessionModel


def model_to_flow_version(model: FlowVersionModel, *, flow_name: str) -> FlowVersion:
    return FlowVersion(
        id=model.id.hex,
        flow_id=model.flow_id.hex,
        status=FlowVersionStatus(model.status),
        flow=definition_to_flow(model.flow_id.hex, flow_name, model.definition),
        version=model.version,
    )


# ── Bot ↔ ORM ────────────────────────────────────────────────────────────────


def bot_to_model(bot: Bot) -> BotModel:
    model = BotModel(
        id=uuid.UUID(bot.id),
        name=bot.name,
        platform=bot.platform,
        token_vault_ref=bot.token.vault_ref,
        status=bot.status,
        flow_id=uuid.UUID(bot.flow_id) if bot.flow_id else None,
        published_flow_version_id=(uuid.UUID(bot.published_flow_version_id) if bot.published_flow_version_id else None),
    )
    if bot.mini_app is not None:
        model.mini_app = mini_app_to_model(bot.mini_app)
    return model


def apply_bot_to_model(bot: Bot, model: BotModel) -> None:
    """Переносит состояние агрегата в существующую ORM-строку (кроме id/platform)."""
    model.name = bot.name
    model.token_vault_ref = bot.token.vault_ref
    model.status = bot.status
    model.flow_id = uuid.UUID(bot.flow_id) if bot.flow_id else None
    model.published_flow_version_id = (
        uuid.UUID(bot.published_flow_version_id) if bot.published_flow_version_id else None
    )
    if bot.mini_app is None:
        model.mini_app = None
    elif model.mini_app is None:
        model.mini_app = mini_app_to_model(bot.mini_app)
    else:
        model.mini_app.url = bot.mini_app.url
        model.mini_app.title = bot.mini_app.title


def mini_app_to_model(mini_app: MiniApp) -> MiniAppModel:
    return MiniAppModel(
        id=uuid.UUID(mini_app.id),
        bot_id=uuid.UUID(mini_app.bot_id),
        url=mini_app.url,
        title=mini_app.title,
    )


def model_to_bot(model: BotModel) -> Bot:
    mini_app = None
    if model.mini_app is not None:
        mini_app = MiniApp(
            id=model.mini_app.id.hex,
            bot_id=model.id.hex,
            url=model.mini_app.url,
            title=model.mini_app.title,
        )
    return Bot(
        id=model.id.hex,
        name=model.name,
        platform=model.platform,
        token=Token(vault_ref=model.token_vault_ref),
        flow_id=model.flow_id.hex if model.flow_id else None,
        status=model.status,
        mini_app=mini_app,
        published_flow_version_id=(model.published_flow_version_id.hex if model.published_flow_version_id else None),
    )


# ── Session ↔ ORM ────────────────────────────────────────────────────────────


def session_to_model(session: Session) -> SessionModel:
    return SessionModel(
        id=uuid.UUID(session.id),
        bot_id=uuid.UUID(session.bot_id),
        external_user_id=session.external_user_id,
        flow_version_id=uuid.UUID(session.flow_version_id) if session.flow_version_id else None,
        current_node_id=session.current_node_id,
        variables=dict(session.variables),
        awaiting_variable=session.awaiting_variable,
        status=session.status,
    )


def apply_session_to_model(session: Session, model: SessionModel) -> None:
    model.flow_version_id = uuid.UUID(session.flow_version_id) if session.flow_version_id else None
    model.current_node_id = session.current_node_id
    model.variables = dict(session.variables)
    model.awaiting_variable = session.awaiting_variable
    model.status = session.status


def model_to_session(model: SessionModel) -> Session:
    return Session(
        id=model.id.hex,
        bot_id=model.bot_id.hex,
        external_user_id=model.external_user_id,
        flow_version_id=model.flow_version_id.hex if model.flow_version_id else None,
        current_node_id=model.current_node_id,
        variables=dict(model.variables),
        awaiting_variable=model.awaiting_variable,
        status=model.status,
    )
