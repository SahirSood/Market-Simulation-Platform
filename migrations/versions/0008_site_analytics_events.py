"""Add first-party deployed-site analytics events.

Revision ID: 0008_site_analytics_events
Revises: 0007_agent_activity_events
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_site_analytics_events"
down_revision = "0007_agent_activity_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_analytics_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("referrer_domain", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("utm_source", sa.String(length=128), nullable=True),
        sa.Column("utm_medium", sa.String(length=128), nullable=True),
        sa.Column("utm_campaign", sa.String(length=128), nullable=True),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("target_domain", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_site_analytics_events_timestamp", "site_analytics_events", ["timestamp"])
    op.create_index("ix_site_analytics_events_event_type", "site_analytics_events", ["event_type"])
    op.create_index("ix_site_analytics_events_path", "site_analytics_events", ["path"])
    op.create_index("ix_site_analytics_events_referrer_domain", "site_analytics_events", ["referrer_domain"])
    op.create_index("ix_site_analytics_events_source", "site_analytics_events", ["source"])
    op.create_index("ix_site_analytics_events_utm_source", "site_analytics_events", ["utm_source"])
    op.create_index("ix_site_analytics_events_utm_campaign", "site_analytics_events", ["utm_campaign"])
    op.create_index("ix_site_analytics_events_target_domain", "site_analytics_events", ["target_domain"])
    op.create_index("ix_site_analytics_events_session_id", "site_analytics_events", ["session_id"])
    op.create_index("ix_site_analytics_events_ip_hash", "site_analytics_events", ["ip_hash"])


def downgrade() -> None:
    op.drop_index("ix_site_analytics_events_ip_hash", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_session_id", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_target_domain", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_utm_campaign", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_utm_source", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_source", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_referrer_domain", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_path", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_event_type", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_timestamp", table_name="site_analytics_events")
    op.drop_table("site_analytics_events")
