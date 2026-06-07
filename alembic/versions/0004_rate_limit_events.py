"""Ajouter les evenements de rate limiting

Revision ID: 0004_rate_limit_events
Revises: 0003_document_chunks
Create Date: 2026-06-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_rate_limit_events"
down_revision: str | Sequence[str] | None = "0003_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("client_key", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rate_limit_events_id"), "rate_limit_events", ["id"], unique=False)
    op.create_index(op.f("ix_rate_limit_events_scope"), "rate_limit_events", ["scope"])
    op.create_index(
        op.f("ix_rate_limit_events_client_key"),
        "rate_limit_events",
        ["client_key"],
    )
    op.create_index(
        op.f("ix_rate_limit_events_created_at"),
        "rate_limit_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rate_limit_events_created_at"), table_name="rate_limit_events")
    op.drop_index(op.f("ix_rate_limit_events_client_key"), table_name="rate_limit_events")
    op.drop_index(op.f("ix_rate_limit_events_scope"), table_name="rate_limit_events")
    op.drop_index(op.f("ix_rate_limit_events_id"), table_name="rate_limit_events")
    op.drop_table("rate_limit_events")
