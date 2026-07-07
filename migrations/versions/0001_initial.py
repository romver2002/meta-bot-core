"""Начальная схема по ADR-0008: bot, mini_app, flow(+versions), custom_code, session, audit, capability_matrix.

Revision ID: 0001
Revises:
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

platform_enum = postgresql.ENUM("telegram", "max", name="platform_enum", create_type=False)
bot_status_enum = postgresql.ENUM("draft", "published", "paused", name="bot_status_enum", create_type=False)
flow_version_status_enum = postgresql.ENUM(
    "draft", "published", "archived", name="flow_version_status_enum", create_type=False
)
session_status_enum = postgresql.ENUM("active", "completed", "expired", name="session_status_enum", create_type=False)
publish_action_enum = postgresql.ENUM(
    "save_draft", "publish", "pause", "resume", "rollback", name="publish_action_enum", create_type=False
)
ENUMS = (platform_enum, bot_status_enum, flow_version_status_enum, session_status_enum, publish_action_enum)


def upgrade() -> None:
    bind = op.get_bind()
    for pg_enum in ENUMS:
        pg_enum.create(bind, checkfirst=True)

    op.create_table(
        "bot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("token_vault_ref", sa.Text(), nullable=False),
        sa.Column("status", bot_status_enum, nullable=False, server_default="draft"),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("published_flow_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "mini_app",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bot.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("url LIKE 'https://%'", name="ck_mini_app_https"),
    )

    op.create_table(
        "flow",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("draft_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "flow_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "flow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flow.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("status", flow_version_status_enum, nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("flow_id", "version", name="uq_flow_version"),
    )
    op.create_index(
        "uq_flow_single_draft",
        "flow_versions",
        ["flow_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "ix_flow_versions_definition",
        "flow_versions",
        ["definition"],
        postgresql_using="gin",
        postgresql_ops={"definition": "jsonb_path_ops"},
    )
    op.create_foreign_key(
        "fk_flow_draft",
        "flow",
        "flow_versions",
        ["draft_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "custom_code_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("code_id", "version", name="uq_custom_code_version"),
    )

    op.create_table(
        "session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_user_id", sa.Text(), nullable=False),
        sa.Column("external_chat_id", sa.Text(), nullable=True),
        sa.Column("flow_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_node_id", sa.Text(), nullable=True),
        sa.Column("variables", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("awaiting_variable", sa.Text(), nullable=True),
        sa.Column("status", session_status_enum, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_session_active",
        "session",
        ["bot_id", "external_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_session_bot", "session", ["bot_id"])

    op.create_table(
        "publish_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("bot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flow_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", publish_action_enum, nullable=False),
        sa.Column("from_status", bot_status_enum, nullable=True),
        sa.Column("to_status", bot_status_enum, nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "capability_matrix",
        sa.Column("platform", platform_enum, primary_key=True),
        sa.Column("capability", sa.Text(), primary_key=True),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_table("capability_matrix")
    op.drop_table("publish_audit")
    op.drop_index("ix_session_bot", table_name="session")
    op.drop_index("uq_session_active", table_name="session")
    op.drop_table("session")
    op.drop_table("custom_code_versions")
    op.drop_constraint("fk_flow_draft", "flow", type_="foreignkey")
    op.drop_index("ix_flow_versions_definition", table_name="flow_versions")
    op.drop_index("uq_flow_single_draft", table_name="flow_versions")
    op.drop_table("flow_versions")
    op.drop_table("flow")
    op.drop_table("mini_app")
    op.drop_table("bot")
    bind = op.get_bind()
    for pg_enum in reversed(ENUMS):
        pg_enum.drop(bind, checkfirst=True)
