"""Persist structured public HOLD causes.

Revision ID: 0012_hold_cause
Revises: 0011_replay_llm_cost_tracking
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_hold_cause"
down_revision = "0011_replay_llm_cost_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bot_decisions",
        sa.Column("hold_cause", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_bot_decisions_hold_cause",
        "bot_decisions",
        ["hold_cause"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bot_decisions_hold_cause", table_name="bot_decisions")
    op.drop_column("bot_decisions", "hold_cause")
