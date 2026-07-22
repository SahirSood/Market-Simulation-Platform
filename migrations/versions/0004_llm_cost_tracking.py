"""Add LLM cost tracking columns.

Revision ID: 0004_llm_cost_tracking
Revises: 0003_phase_g_audit_events
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_llm_cost_tracking"
down_revision = "0003_phase_g_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bot_decisions", sa.Column("llm_input_tokens", sa.Integer(), nullable=True))
    op.add_column("bot_decisions", sa.Column("llm_output_tokens", sa.Integer(), nullable=True))
    op.add_column("bot_decisions", sa.Column("llm_total_tokens", sa.Integer(), nullable=True))
    op.add_column("bot_decisions", sa.Column("llm_estimated_cost_usd", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("bot_decisions", "llm_estimated_cost_usd")
    op.drop_column("bot_decisions", "llm_total_tokens")
    op.drop_column("bot_decisions", "llm_output_tokens")
    op.drop_column("bot_decisions", "llm_input_tokens")
