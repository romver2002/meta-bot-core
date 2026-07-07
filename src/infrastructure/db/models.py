"""ORM-модели хранения (ADR-0008, DDL — specs/001-persistence/design.md).

Только infrastructure: домен эти классы не видит, перевод домен↔ORM — в
mappers.py. Внутри агрегата — жёсткие FK; между агрегатами — ссылки по id
без FK (граница агрегата = граница транзакции).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.bot.value_objects import BotStatus, Platform
from domain.flow.version import FlowVersionStatus


class SessionStatus(enum.StrEnum):
    """Жизненный цикл durable-снапшота сессии (инфраструктурный)."""

    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class PublishAction(enum.StrEnum):
    """Действие в append-only журнале публикаций."""

    SAVE_DRAFT = "save_draft"
    PUBLISH = "publish"
    PAUSE = "pause"
    RESUME = "resume"
    ROLLBACK = "rollback"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> sa.Enum:
    return sa.Enum(enum_cls, name=name, values_callable=lambda e: [member.value for member in e])


platform_enum = _pg_enum(Platform, "platform_enum")
bot_status_enum = _pg_enum(BotStatus, "bot_status_enum")
flow_version_status_enum = _pg_enum(FlowVersionStatus, "flow_version_status_enum")
session_status_enum = _pg_enum(SessionStatus, "session_status_enum")
publish_action_enum = _pg_enum(PublishAction, "publish_action_enum")


class Base(DeclarativeBase):
    """Общая декларативная база моделей meta-bot-core."""


class BotModel(Base):
    """Агрегат Bot: платформа + ссылка на токен в vault + исполняемая версия сценария."""

    __tablename__ = "bot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(sa.Text, default="")
    platform: Mapped[Platform] = mapped_column(platform_enum)
    token_vault_ref: Mapped[str] = mapped_column(sa.Text)  # хэндл записи в vault, НЕ секрет
    status: Mapped[BotStatus] = mapped_column(bot_status_enum, default=BotStatus.DRAFT)
    flow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)  # soft-ref, 1—1
    published_flow_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # soft-ref
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
    row_version: Mapped[int] = mapped_column(sa.Integer, default=0)

    mini_app: Mapped[MiniAppModel | None] = relationship(back_populates="bot", cascade="all, delete-orphan")


class MiniAppModel(Base):
    """MiniApp — внутри агрегата Bot (0..1 на бота); HTTPS — defense-in-depth к BR-003."""

    __tablename__ = "mini_app"
    __table_args__ = (sa.CheckConstraint("url LIKE 'https://%'", name="ck_mini_app_https"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("bot.id", ondelete="CASCADE"), unique=True
    )
    url: Mapped[str] = mapped_column(sa.Text)
    title: Mapped[str] = mapped_column(sa.Text, default="")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    bot: Mapped[BotModel] = relationship(back_populates="mini_app")


class FlowModel(Base):
    """Агрегат Flow: тонкий head; графы живут в иммутабельных flow_versions."""

    __tablename__ = "flow"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    bot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # обратная soft-ref
    name: Mapped[str] = mapped_column(sa.Text, default="")
    draft_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "flow_versions.id",
            name="fk_flow_draft",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )


class FlowVersionModel(Base):
    """Версия сценария: definition JSONB — весь граф одним документом."""

    __tablename__ = "flow_versions"
    __table_args__ = (
        sa.UniqueConstraint("flow_id", "version", name="uq_flow_version"),
        sa.Index(
            "uq_flow_single_draft",
            "flow_id",
            unique=True,
            postgresql_where=sa.text("status = 'draft'"),
        ),
        sa.Index(
            "ix_flow_versions_definition",
            "definition",
            postgresql_using="gin",
            postgresql_ops={"definition": "jsonb_path_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    flow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("flow.id", ondelete="CASCADE"))
    version: Mapped[int | None] = mapped_column(sa.Integer)  # NULL у черновика
    status: Mapped[FlowVersionStatus] = mapped_column(flow_version_status_enum)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[int] = mapped_column(sa.SmallInteger, default=1)
    content_hash: Mapped[str] = mapped_column(sa.Text)
    row_version: Mapped[int] = mapped_column(sa.Integer, default=0)  # оптимистический лок черновика
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class CustomCodeVersionModel(Base):
    """Версии пользовательского Python-блока (BR-004). Строки иммутабельны."""

    __tablename__ = "custom_code_versions"
    __table_args__ = (sa.UniqueConstraint("code_id", "version", name="uq_custom_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(sa.Integer)
    source: Mapped[str] = mapped_column(sa.Text)  # данные; исполняется только в песочнице
    content_hash: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SessionModel(Base):
    """Durable-снапшот FSM-состояния (горячее состояние — Redis, ADR-0008)."""

    __tablename__ = "session"
    __table_args__ = (
        sa.Index(
            "uq_session_active",
            "bot_id",
            "external_user_id",
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
        ),
        sa.Index("ix_session_bot", "bot_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))  # soft-ref (кросс-агрегат)
    external_user_id: Mapped[str] = mapped_column(sa.Text)  # ПДн
    external_chat_id: Mapped[str | None] = mapped_column(sa.Text)  # ПДн
    flow_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # пин версии
    current_node_id: Mapped[str | None] = mapped_column(sa.Text)  # id узла внутри JSONB-графа
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    awaiting_variable: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[SessionStatus] = mapped_column(session_status_enum, default=SessionStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
    last_event_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class PublishAuditModel(Base):
    """Append-only журнал публикаций/lifecycle; без секретов и ПДн в meta."""

    __tablename__ = "publish_audit"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    bot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    flow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    flow_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[PublishAction] = mapped_column(publish_action_enum)
    from_status: Mapped[BotStatus | None] = mapped_column(bot_status_enum)
    to_status: Mapped[BotStatus | None] = mapped_column(bot_status_enum)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CapabilityMatrixModel(Base):
    """CapabilityMatrix как seed-данные: различия платформ — данными (BR-005/BR-006)."""

    __tablename__ = "capability_matrix"

    platform: Mapped[Platform] = mapped_column(platform_enum, primary_key=True)
    capability: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    available: Mapped[bool] = mapped_column(sa.Boolean, default=True)
