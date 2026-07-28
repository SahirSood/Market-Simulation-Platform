"""Add geolocation fields to site analytics events.

Revision ID: 0009_site_analytics_geo
Revises: 0008_site_analytics_events
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_site_analytics_geo"
down_revision = "0008_site_analytics_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("site_analytics_events", sa.Column("geo_country", sa.String(length=128), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_country_code", sa.String(length=8), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_region", sa.String(length=128), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_city", sa.String(length=128), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_timezone", sa.String(length=64), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_continent", sa.String(length=64), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_org", sa.String(length=255), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_asn", sa.String(length=64), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_latitude", sa.Float(), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_longitude", sa.Float(), nullable=True))
    op.add_column("site_analytics_events", sa.Column("geo_source", sa.String(length=32), nullable=True))
    op.create_index("ix_site_analytics_events_geo_country_code", "site_analytics_events", ["geo_country_code"])
    op.create_index("ix_site_analytics_events_geo_city", "site_analytics_events", ["geo_city"])
    op.create_index("ix_site_analytics_events_geo_timezone", "site_analytics_events", ["geo_timezone"])
    op.create_index("ix_site_analytics_events_geo_org", "site_analytics_events", ["geo_org"])


def downgrade() -> None:
    op.drop_index("ix_site_analytics_events_geo_org", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_geo_timezone", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_geo_city", table_name="site_analytics_events")
    op.drop_index("ix_site_analytics_events_geo_country_code", table_name="site_analytics_events")
    op.drop_column("site_analytics_events", "geo_source")
    op.drop_column("site_analytics_events", "geo_longitude")
    op.drop_column("site_analytics_events", "geo_latitude")
    op.drop_column("site_analytics_events", "geo_asn")
    op.drop_column("site_analytics_events", "geo_org")
    op.drop_column("site_analytics_events", "geo_continent")
    op.drop_column("site_analytics_events", "geo_timezone")
    op.drop_column("site_analytics_events", "geo_city")
    op.drop_column("site_analytics_events", "geo_region")
    op.drop_column("site_analytics_events", "geo_country_code")
    op.drop_column("site_analytics_events", "geo_country")
