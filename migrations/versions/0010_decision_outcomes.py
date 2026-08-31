"""Add decision outcome labels.

Revision ID: 0010_decision_outcomes
Revises: 0009_site_analytics_geo
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_decision_outcomes"
down_revision = "0009_site_analytics_geo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("bot_decisions.id"), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("bot_name", sa.String(length=64), nullable=False),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("decision_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("horizon_seconds", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("mark_price", sa.Float(), nullable=True),
        sa.Column("portfolio_value_at_decision", sa.Float(), nullable=True),
        sa.Column("portfolio_value_at_observation", sa.Float(), nullable=True),
        sa.Column("position_pnl", sa.Float(), nullable=True),
        sa.Column("portfolio_delta", sa.Float(), nullable=True),
        sa.Column("llm_estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("net_after_llm_cost", sa.Float(), nullable=True),
        sa.Column("filled_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_approved", sa.Boolean(), nullable=True),
        sa.Column("outcome_status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "decision_id",
            "horizon",
            name="uq_decision_outcomes_decision_horizon",
        ),
    )
    op.create_index("ix_decision_outcomes_bot_id", "decision_outcomes", ["bot_id"])
    op.create_index("ix_decision_outcomes_decision_id", "decision_outcomes", ["decision_id"])
    op.create_index("ix_decision_outcomes_decision_timestamp", "decision_outcomes", ["decision_timestamp"])
    op.create_index("ix_decision_outcomes_horizon", "decision_outcomes", ["horizon"])
    op.create_index("ix_decision_outcomes_llm_provider", "decision_outcomes", ["llm_provider"])
    op.create_index("ix_decision_outcomes_observed_at", "decision_outcomes", ["observed_at"])
    op.create_index("ix_decision_outcomes_outcome_status", "decision_outcomes", ["outcome_status"])
    op.create_index("ix_decision_outcomes_ticker", "decision_outcomes", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_decision_outcomes_ticker", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_outcome_status", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_observed_at", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_llm_provider", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_horizon", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_decision_timestamp", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_decision_id", table_name="decision_outcomes")
    op.drop_index("ix_decision_outcomes_bot_id", table_name="decision_outcomes")
    op.drop_table("decision_outcomes")
