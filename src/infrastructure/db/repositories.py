"""Pg-реализации портов хранения (ADR-0008): PgBotRepository, PgFlowRepository, PgSessionRepository.

Граница агрегата = граница транзакции: каждый метод — одна транзакция.
Доменные объекты пересекают границу, ORM-модели — никогда.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from application.errors import ConcurrencyError, FlowNotFoundError
from domain.bot.entities import Bot
from domain.flow.entities import Flow
from domain.flow.version import FlowVersion, FlowVersionStatus
from domain.session.entities import Session
from infrastructure.db import mappers
from infrastructure.db.models import (
    BotModel,
    FlowModel,
    FlowVersionModel,
    PublishAction,
    PublishAuditModel,
    SessionModel,
    SessionStatus,
)


class PgBotRepository:
    """Хранилище агрегата Bot (реализация порта BotRepository)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, bot_id: str) -> Bot | None:
        async with self._session_factory() as db:
            model = await db.get(BotModel, uuid.UUID(bot_id), options=[selectinload(BotModel.mini_app)])
            return mappers.model_to_bot(model) if model is not None else None

    async def save(self, bot: Bot) -> None:
        async with self._session_factory() as db, db.begin():
            model = await db.get(BotModel, uuid.UUID(bot.id), options=[selectinload(BotModel.mini_app)])
            if model is None:
                db.add(mappers.bot_to_model(bot))
            else:
                mappers.apply_bot_to_model(bot, model)
                model.row_version += 1


class PgFlowRepository:
    """Хранилище сценариев: черновик in-place + иммутабельные published-версии."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_draft(self, flow_id: str) -> Flow | None:
        async with self._session_factory() as db:
            result = await db.execute(
                sa.select(FlowModel, FlowVersionModel)
                .join(FlowVersionModel, FlowModel.draft_version_id == FlowVersionModel.id)
                .where(FlowModel.id == uuid.UUID(flow_id))
            )
            pair = result.first()
            if pair is None:
                return None
            flow_model, draft = pair
            return mappers.definition_to_flow(flow_id, flow_model.name, draft.definition)

    async def save_draft(self, flow: Flow, *, expected_row_version: int | None = None) -> int:
        definition = mappers.flow_to_definition(flow)
        digest = mappers.definition_hash(definition)
        async with self._session_factory() as db, db.begin():
            flow_uuid = uuid.UUID(flow.id)
            flow_model = await db.get(FlowModel, flow_uuid, with_for_update=True)
            if flow_model is None:
                flow_model = FlowModel(id=flow_uuid, name=flow.name)
                db.add(flow_model)
            else:
                flow_model.name = flow.name

            draft: FlowVersionModel | None = None
            if flow_model.draft_version_id is not None:
                draft = await db.get(FlowVersionModel, flow_model.draft_version_id, with_for_update=True)

            if draft is None:
                draft = FlowVersionModel(
                    id=uuid.uuid4(),
                    flow_id=flow_uuid,
                    status=FlowVersionStatus.DRAFT,
                    definition=definition,
                    content_hash=digest,
                )
                db.add(draft)
                await db.flush()
                flow_model.draft_version_id = draft.id
                return draft.row_version

            if expected_row_version is not None and draft.row_version != expected_row_version:
                raise ConcurrencyError(
                    f"Черновик {flow.id!r} изменён конкурентно: "
                    f"row_version={draft.row_version}, ожидался {expected_row_version}"
                )
            draft.definition = definition
            draft.content_hash = digest
            draft.row_version += 1
            return draft.row_version

    async def publish(self, flow_id: str) -> FlowVersion:
        async with self._session_factory() as db, db.begin():
            flow_uuid = uuid.UUID(flow_id)
            flow_model = await db.get(FlowModel, flow_uuid, with_for_update=True)
            if flow_model is None or flow_model.draft_version_id is None:
                raise FlowNotFoundError(f"У сценария {flow_id!r} нет черновика для публикации")
            draft = await db.get(FlowVersionModel, flow_model.draft_version_id)
            if draft is None:
                raise FlowNotFoundError(f"Черновик сценария {flow_id!r} не найден")

            next_version = (
                await db.scalar(
                    sa.select(sa.func.coalesce(sa.func.max(FlowVersionModel.version), 0)).where(
                        FlowVersionModel.flow_id == flow_uuid
                    )
                )
                or 0
            ) + 1
            published = FlowVersionModel(
                id=uuid.uuid4(),
                flow_id=flow_uuid,
                version=next_version,
                status=FlowVersionStatus.PUBLISHED,
                definition=draft.definition,
                schema_version=draft.schema_version,
                content_hash=draft.content_hash,
                published_at=sa.func.now(),
            )
            db.add(published)
            db.add(
                PublishAuditModel(
                    bot_id=flow_model.bot_id,
                    flow_id=flow_uuid,
                    flow_version_id=published.id,
                    action=PublishAction.PUBLISH,
                )
            )
            await db.flush()
            await db.refresh(published)
            return mappers.model_to_flow_version(published, flow_name=flow_model.name)

    async def get_version(self, flow_version_id: str) -> FlowVersion | None:
        async with self._session_factory() as db:
            result = await db.execute(
                sa.select(FlowVersionModel, FlowModel.name)
                .join(FlowModel, FlowVersionModel.flow_id == FlowModel.id)
                .where(FlowVersionModel.id == uuid.UUID(flow_version_id))
            )
            pair = result.first()
            if pair is None:
                return None
            model, flow_name = pair
            return mappers.model_to_flow_version(model, flow_name=flow_name)

    async def list_versions(self, flow_id: str) -> list[FlowVersion]:
        async with self._session_factory() as db:
            result = await db.execute(
                sa.select(FlowVersionModel, FlowModel.name)
                .join(FlowModel, FlowVersionModel.flow_id == FlowModel.id)
                .where(FlowVersionModel.flow_id == uuid.UUID(flow_id))
                .order_by(FlowVersionModel.version.desc().nulls_first())
            )
            return [mappers.model_to_flow_version(model, flow_name=flow_name) for model, flow_name in result.all()]


class PgSessionRepository:
    """Durable-хранилище Session; единственность активной держит partial-unique индекс."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_active(self, bot_id: str, external_user_id: str) -> Session | None:
        async with self._session_factory() as db:
            model = await db.scalar(
                sa.select(SessionModel).where(
                    SessionModel.bot_id == uuid.UUID(bot_id),
                    SessionModel.external_user_id == external_user_id,
                    SessionModel.status == SessionStatus.ACTIVE,
                )
            )
            return mappers.model_to_session(model) if model is not None else None

    async def save(self, session: Session) -> None:
        try:
            async with self._session_factory() as db, db.begin():
                model = await db.get(SessionModel, uuid.UUID(session.id), with_for_update=True)
                if model is None:
                    db.add(mappers.session_to_model(session))
                else:
                    mappers.apply_session_to_model(session, model)
        except IntegrityError as exc:  # uq_session_active: вторая активная на (Bot, пользователь)
            raise ConcurrencyError(
                f"Активная Session для (bot={session.bot_id}, user={session.external_user_id}) уже существует"
            ) from exc
