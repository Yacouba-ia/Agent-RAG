"""Strengthen constraints and indexes

Revision ID: 0002_constraints_indexes
Revises: 0001_initial_schema
Create Date: 2026-06-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_constraints_indexes"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "is_active", existing_type=sa.Boolean(), nullable=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.alter_column("chat_sessions", "user_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "chat_sessions",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.alter_column(
        "chat_sessions",
        "update_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.create_index(op.f("ix_chat_sessions_thread_id"), "chat_sessions", ["thread_id"])
    op.create_index(op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"])
    op.create_unique_constraint(
        "uq_chat_sessions_user_thread",
        "chat_sessions",
        ["user_id", "thread_id"],
    )

    op.alter_column("chat_messages", "session_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "chat_messages",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.alter_column(
        "chat_messages",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None,
    )
    op.alter_column("chat_messages", "session_id", existing_type=sa.Integer(), nullable=True)

    op.drop_constraint("uq_chat_sessions_user_thread", "chat_sessions", type_="unique")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_thread_id"), table_name="chat_sessions")
    op.alter_column(
        "chat_sessions",
        "update_at",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "chat_sessions",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None,
    )
    op.alter_column("chat_sessions", "user_id", existing_type=sa.Integer(), nullable=True)

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.alter_column("users", "is_active", existing_type=sa.Boolean(), nullable=True)
