"""add outbox table for outbox pattern

Revision ID: a1b2c3d4e5f6
Revises: 923509e24aee
Create Date: 2026-06-09 15:50:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "923509e24aee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox",
        sa.Column("id", sa.String(40), nullable=False),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(40), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("routing_key", sa.String(200), nullable=True),
        sa.Column("exchange", sa.String(100), nullable=True),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_processed_created", "outbox", ["processed", "created_at"])


def downgrade() -> None:
    op.drop_table("outbox")
