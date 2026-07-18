"""Add Phase G audit events.

Revision ID: 0003_phase_g_audit_events
Revises: 0002_rag_job_status
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_phase_g_audit_events"
down_revision = "0002_rag_job_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phase_g_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("auth_method", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_phase_g_audit_events_timestamp", "phase_g_audit_events", ["timestamp"])
    op.create_index("ix_phase_g_audit_events_action", "phase_g_audit_events", ["action"])
    op.create_index("ix_phase_g_audit_events_status", "phase_g_audit_events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_phase_g_audit_events_status", table_name="phase_g_audit_events")
    op.drop_index("ix_phase_g_audit_events_action", table_name="phase_g_audit_events")
    op.drop_index("ix_phase_g_audit_events_timestamp", table_name="phase_g_audit_events")
    op.drop_table("phase_g_audit_events")
