"""Pg-реализации портов хранения (ADR-0008): PgBotRepository, PgFlowRepository, PgSessionRepository.

Граница агрегата = граница транзакции: каждый метод — одна транзакция.
Доменные объекты пересекают границу, ORM-модели — никогда. Тексты ошибок
не содержат ПДн (external_user_id) и секретов (architecture/security.md).
"""

from __future__ import annotations

import datetime
import uuid
from typing import cast

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from application.errors import BotCreationError, ConcurrencyError, FlowNotFoundError
from application.ports.flow_repository import FlowDraft
from domain.bot.entities import Bot
from domain.flow.codec import definition_hash, definition_to_flow, flow_to_definition
from domain.flow.entities import Flow
from domain.flow.version import FlowVersion, FlowVersionStatus
from domain.session.entities import Session, SessionStatus
from infrastructure.db import mappers
from infrastructure.db.models import (
    BotModel,
    FlowModel,
    FlowVersionModel,
    PublishAction,
    PublishAuditModel,
    SessionModel,
)


class PgBotRepository:
    """Хранилище агрегата Bot (реализация порта BotRepository)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, bot_id: str) -> Bot | None:
        # bot_id приходит из URL (admin/webhook): не-UUID — «такого бота нет»
        # (None -> 404 на границе), а не ValueError -> 500 из глубины стека.
        try:
            key = uuid.UUID(bot_id)
        except ValueError:
            return None
        async with self._session_factory() as db:
            model = await db.get(BotModel, key, options=[selectinload(BotModel.mini_app)])
            return mappers.model_to_bot(model) if model is not None else None

    async def find_by_token_fingerprint(self, fingerprint: str) -> Bot | None:
        async with self._session_factory() as db:
            result = await db.execute(
                sa.select(BotModel)
                .options(selectinload(BotModel.mini_app))
                .where(BotModel.token_hash == fingerprint)
            )
            model = result.scalars().first()
            return mappers.model_to_bot(model) if model is not None else None

    async def list_all(self) -> list[Bot]:
        async with self._session_factory() as db:
            result = await db.execute(
                sa.select(BotModel)
                .options(selectinload(BotModel.mini_app))
                .order_by(BotModel.created_at.desc(), BotModel.id)
            )
            return [mappers.model_to_bot(model) for model in result.scalars()]

    async def save(self, bot: Bot) -> None:
        # Строка блокируется на время транзакции (FOR UPDATE) — read-modify-write
        # внутри save атомарен. Optimistic lock между get() и save() —
        # зафиксированный долг до появления конкурентных админ-сценариев (IAM).
        try:
            async with self._session_factory() as db, db.begin():
                model = await db.get(
                    BotModel,
                    uuid.UUID(bot.id),
                    options=[selectinload(BotModel.mini_app)],
                    with_for_update=True,
                )
                if model is None:
                    db.add(mappers.bot_to_model(bot))
                else:
                    mappers.apply_bot_to_model(bot, model)
                    model.row_version += 1
        except IntegrityError as exc:
            # Гонка двух connect с одним токеном: уникальный индекс token_hash.
            # Ретрай попадёт в find_by_token_fingerprint и вернёт существующего.
            raise BotCreationError(
                "Бот с этим токеном уже подключён — повторите подключение"
            ) from exc


class PgFlowRepository:
    """Хранилище сценариев: черновик in-place + иммутабельные published-версии."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_draft(self, flow_id: str) -> FlowDraft | None:
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
            return FlowDraft(
                flow=definition_to_flow(flow_id, flow_model.name, draft.definition),
                row_version=draft.row_version,
            )

    async def save_draft(self, flow: Flow, *, expected_row_version: int | None) -> int:
        definition = flow_to_definition(flow)
        digest = definition_hash(definition)
        try:
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
                    if expected_row_version is not None:
                        raise ConcurrencyError(
                            f"Черновика {flow.id!r} не существует (ожидался row_version={expected_row_version})"
                        )
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

                if expected_row_version is None:
                    raise ConcurrencyError(
                        f"Черновик {flow.id!r} уже существует — слепая перезапись запрещена, "
                        "передайте expected_row_version из get_draft"
                    )
                if draft.row_version != expected_row_version:
                    raise ConcurrencyError(
                        f"Черновик {flow.id!r} изменён конкурентно: "
                        f"row_version={draft.row_version}, ожидался {expected_row_version}"
                    )
                draft.definition = definition
                draft.content_hash = digest
                draft.row_version += 1
                return draft.row_version
        except IntegrityError as exc:  # гонка первого создания (pk flow / uq_flow_single_draft)
            raise ConcurrencyError(f"Черновик {flow.id!r} создаётся конкурентно") from exc

    async def publish(
        self,
        flow_id: str,
        *,
        expected_row_version: int,
        bot_id: str | None = None,
        actor_id: str | None = None,
    ) -> FlowVersion:
        async with self._session_factory() as db, db.begin():
            flow_uuid = uuid.UUID(flow_id)
            flow_model = await db.get(FlowModel, flow_uuid, with_for_update=True)
            if flow_model is None or flow_model.draft_version_id is None:
                raise FlowNotFoundError(f"У сценария {flow_id!r} нет черновика для публикации")
            draft = await db.get(FlowVersionModel, flow_model.draft_version_id, with_for_update=True)
            if draft is None:
                raise FlowNotFoundError(f"Черновик сценария {flow_id!r} не найден")
            if draft.row_version != expected_row_version:
                # Анти-TOCTOU: публикуется ровно провалидированный снапшот.
                raise ConcurrencyError(
                    f"Черновик {flow_id!r} изменён после валидации: "
                    f"row_version={draft.row_version}, ожидался {expected_row_version}"
                )

            bot_uuid = uuid.UUID(bot_id) if bot_id else None
            if bot_uuid is not None and flow_model.bot_id is None:
                flow_model.bot_id = bot_uuid  # обратная soft-ref для журнала публикаций

            latest = await db.scalar(
                sa.select(FlowVersionModel)
                .where(
                    FlowVersionModel.flow_id == flow_uuid,
                    FlowVersionModel.status == FlowVersionStatus.PUBLISHED,
                )
                .order_by(FlowVersionModel.version.desc())
                .limit(1)
            )
            if latest is not None and latest.content_hash == draft.content_hash:
                # Идемпотентный ретрай: неизменённый черновик -> та же версия.
                return mappers.model_to_flow_version(latest, flow_name=flow_model.name)

            next_version = (latest.version or 0) + 1 if latest is not None else 1
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
                    bot_id=bot_uuid if bot_uuid is not None else flow_model.bot_id,
                    flow_id=flow_uuid,
                    flow_version_id=published.id,
                    action=PublishAction.PUBLISH,
                    actor_id=uuid.UUID(actor_id) if actor_id else None,
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
        except IntegrityError as exc:  # uq_session_active: вторая активная на пару (Bot, user)
            # ПДн (external_user_id) в текст ошибки не попадает.
            raise ConcurrencyError(
                f"Активная Session уже существует (bot={session.bot_id}, session={session.id})"
            ) from exc

    # ── ретеншен ПДн (BR-008, SessionRetentionPort) ──────────────────────────

    async def expire_idle(self, cutoff: datetime.datetime) -> int:
        """Активные сессии без событий с cutoff -> expired, переменные стёрты.

        Семантика стирания — зеркало доменного ``Session.expire()`` (канон);
        критерий простоя — ``last_event_at`` (мапперы штампуют его на каждый
        обработанный event), fallback ``updated_at`` для строк до BR-008.
        """
        async with self._session_factory() as db, db.begin():
            result = cast(
                "sa.CursorResult[object]",
                await db.execute(
                    sa.update(SessionModel)
                    .where(
                        SessionModel.status == SessionStatus.ACTIVE,
                        sa.func.coalesce(SessionModel.last_event_at, SessionModel.updated_at) < cutoff,
                    )
                    .values(status=SessionStatus.EXPIRED, variables={}, awaiting_variable=None)
                ),
            )
            return int(result.rowcount or 0)

    async def delete_finished_before(self, cutoff: datetime.datetime) -> int:
        """Стирает завершённые/просроченные сессии старше срока хранения целиком."""
        async with self._session_factory() as db, db.begin():
            result = cast(
                "sa.CursorResult[object]",
                await db.execute(
                    sa.delete(SessionModel).where(
                        SessionModel.status != SessionStatus.ACTIVE,
                        SessionModel.updated_at < cutoff,
                    )
                ),
            )
            return int(result.rowcount or 0)
