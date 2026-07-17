"""Add RAG ops job status.

Revision ID: 0002_rag_job_status
Revises: 0001_initial_schema
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_rag_job_status"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_job_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, default=0),
        sa.Column("max_attempts", sa.Integer(), nullable=False, default=1),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_rag_job_status_job_type", "rag_job_status", ["job_type"])
    op.create_index("ix_rag_job_status_status", "rag_job_status", ["status"])


def downgrade() -> None:
    op.drop_index("ix_rag_job_status_status", table_name="rag_job_status")
    op.drop_index("ix_rag_job_status_job_type", table_name="rag_job_status")
    op.drop_table("rag_job_status")
