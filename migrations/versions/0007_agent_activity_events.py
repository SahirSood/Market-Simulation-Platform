"""Add public-safe agent activity events.

Revision ID: 0007_agent_activity_events
Revises: 0006_llm_call_made_column
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_agent_activity_events"
down_revision = "0006_llm_call_made_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_activity_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("bot_decisions.id"), nullable=True),
        sa.Column("bot_id", sa.String(length=64), nullable=True),
        sa.Column("bot_name", sa.String(length=64), nullable=True),
        sa.Column("llm_provider", sa.String(length=32), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_agent_activity_events_timestamp", "agent_activity_events", ["timestamp"])
    op.create_index("ix_agent_activity_events_decision_id", "agent_activity_events", ["decision_id"])
    op.create_index("ix_agent_activity_events_bot_id", "agent_activity_events", ["bot_id"])
    op.create_index("ix_agent_activity_events_llm_provider", "agent_activity_events", ["llm_provider"])
    op.create_index("ix_agent_activity_events_event_type", "agent_activity_events", ["event_type"])
    op.create_index("ix_agent_activity_events_stage", "agent_activity_events", ["stage"])
    op.create_index("ix_agent_activity_events_tool_name", "agent_activity_events", ["tool_name"])
    op.create_index("ix_agent_activity_events_status", "agent_activity_events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_agent_activity_events_status", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_tool_name", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_stage", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_event_type", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_llm_provider", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_bot_id", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_decision_id", table_name="agent_activity_events")
    op.drop_index("ix_agent_activity_events_timestamp", table_name="agent_activity_events")
    op.drop_table("agent_activity_events")
