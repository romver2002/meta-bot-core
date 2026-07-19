"""Отпечаток токена у бота — идемпотентное подключение (ADR-0016, BR-009).

SHA-256 токена (не сам секрет): повторный connect того же токена возвращает
существующего бота вместо создания дубля. NULL — у ботов, подключённых до
введения отпечатка (уникальный индекс NULL не ограничивает).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bot", sa.Column("token_hash", sa.Text(), nullable=True))
    op.create_index("ix_bot_token_hash", "bot", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_bot_token_hash", table_name="bot")
    op.drop_column("bot", "token_hash")
