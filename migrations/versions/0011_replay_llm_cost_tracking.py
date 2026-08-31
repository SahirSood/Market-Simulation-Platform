"""Add LLM cost tracking to replay decisions.

Revision ID: 0011_replay_llm_cost_tracking
Revises: 0010_decision_outcomes
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_replay_llm_cost_tracking"
down_revision = "0010_decision_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phase_d_replay_decisions", sa.Column("llm_input_tokens", sa.Integer(), nullable=True))
    op.add_column("phase_d_replay_decisions", sa.Column("llm_output_tokens", sa.Integer(), nullable=True))
    op.add_column("phase_d_replay_decisions", sa.Column("llm_total_tokens", sa.Integer(), nullable=True))
    op.add_column("phase_d_replay_decisions", sa.Column("llm_estimated_cost_usd", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("phase_d_replay_decisions", "llm_estimated_cost_usd")
    op.drop_column("phase_d_replay_decisions", "llm_total_tokens")
    op.drop_column("phase_d_replay_decisions", "llm_output_tokens")
    op.drop_column("phase_d_replay_decisions", "llm_input_tokens")
