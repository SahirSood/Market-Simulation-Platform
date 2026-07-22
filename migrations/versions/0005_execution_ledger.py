"""Add durable execution order and fill ledger.

Revision ID: 0005_execution_ledger
Revises: 0004_llm_cost_tracking
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_execution_ledger"
down_revision = "0004_llm_cost_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("bot_decisions.id"), nullable=True),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("bot_name", sa.String(length=64), nullable=False),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("engine_order_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("order_type", sa.String(length=16), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("submitted_price", sa.Float(), nullable=True),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("fill_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fill_qty_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fill_avg_price", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("portfolio_snapshot", sa.JSON(), nullable=False),
    )
    op.create_index("ix_execution_orders_bot_id", "execution_orders", ["bot_id"])
    op.create_index("ix_execution_orders_decision_id", "execution_orders", ["decision_id"])
    op.create_index("ix_execution_orders_engine_order_id", "execution_orders", ["engine_order_id"])
    op.create_index("ix_execution_orders_status", "execution_orders", ["status"])
    op.create_index("ix_execution_orders_ticker", "execution_orders", ["ticker"])

    op.create_table(
        "execution_fills",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("execution_order_id", sa.Integer(), sa.ForeignKey("execution_orders.id"), nullable=False),
        sa.Column("engine_order_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
    )
    op.create_index("ix_execution_fills_bot_id", "execution_fills", ["bot_id"])
    op.create_index("ix_execution_fills_engine_order_id", "execution_fills", ["engine_order_id"])
    op.create_index("ix_execution_fills_execution_order_id", "execution_fills", ["execution_order_id"])
    op.create_index("ix_execution_fills_ticker", "execution_fills", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_execution_fills_ticker", table_name="execution_fills")
    op.drop_index("ix_execution_fills_execution_order_id", table_name="execution_fills")
    op.drop_index("ix_execution_fills_engine_order_id", table_name="execution_fills")
    op.drop_index("ix_execution_fills_bot_id", table_name="execution_fills")
    op.drop_table("execution_fills")

    op.drop_index("ix_execution_orders_ticker", table_name="execution_orders")
    op.drop_index("ix_execution_orders_status", table_name="execution_orders")
    op.drop_index("ix_execution_orders_engine_order_id", table_name="execution_orders")
    op.drop_index("ix_execution_orders_decision_id", table_name="execution_orders")
    op.drop_index("ix_execution_orders_bot_id", table_name="execution_orders")
    op.drop_table("execution_orders")
