"""Persist structured HOLD causes for replay decisions.

Revision ID: 0013_replay_hold_cause
Revises: 0012_hold_cause
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_replay_hold_cause"
down_revision = "0012_hold_cause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "phase_d_replay_decisions",
        sa.Column("hold_cause", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("phase_d_replay_decisions", "hold_cause")
