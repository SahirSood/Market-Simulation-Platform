"""Add explicit LLM call-made column.

Revision ID: 0006_llm_call_made_column
Revises: 0005_execution_ledger
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_llm_call_made_column"
down_revision = "0005_execution_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("bot_decisions")}
    if "llm_call_made" not in columns:
        op.add_column("bot_decisions", sa.Column("llm_call_made", sa.Boolean(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("bot_decisions")}
    if "llm_call_made" in columns:
        op.drop_column("bot_decisions", "llm_call_made")
