"""Initial live, RAG, and replay schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("bot_name", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("headline_used", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=True),
        sa.Column("evidence_urls", sa.JSON(), nullable=True),
        sa.Column("speculative", sa.Boolean(), nullable=True),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("fill_count", sa.Integer(), nullable=True),
        sa.Column("fill_qty_total", sa.Integer(), nullable=True),
        sa.Column("fill_avg_price", sa.Float(), nullable=True),
        sa.Column("model_metadata", sa.JSON(), nullable=True),
        sa.Column("portfolio_snapshot", sa.JSON(), nullable=False),
    )
    op.create_index("ix_bot_decisions_bot_id", "bot_decisions", ["bot_id"])

    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("form_type", sa.String(length=32), nullable=True),
        sa.Column("cik", sa.String(length=10), nullable=True),
        sa.Column("accession_no", sa.String(length=32), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rag_documents_ticker", "rag_documents", ["ticker"])
    op.create_index("ix_rag_documents_content_hash", "rag_documents", ["content_hash"])
    op.create_index("ix_rag_documents_ticker_form", "rag_documents", ["ticker", "form_type"])

    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("rag_documents.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_pos", sa.Integer(), nullable=True),
        sa.Column("end_pos", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rag_chunks_document_id", "rag_chunks", ["document_id"])
    op.create_index("ix_rag_chunks_content", "rag_chunks", ["content"])

    op.create_table(
        "phase_d_replay_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "phase_d_replay_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("phase_d_replay_runs.id"), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("as_of_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("bot_name", sa.String(length=64), nullable=False),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("headline_used", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_urls", sa.JSON(), nullable=False),
        sa.Column("speculative", sa.String(length=8), nullable=False),
        sa.Column("risk_approved", sa.Boolean(), nullable=True),
        sa.Column("risk_reason", sa.Text(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("fill_count", sa.Integer(), nullable=False),
        sa.Column("fill_qty_total", sa.Integer(), nullable=False),
        sa.Column("fill_avg_price", sa.Float(), nullable=True),
        sa.Column("model_metadata", sa.JSON(), nullable=True),
        sa.Column("portfolio_snapshot", sa.JSON(), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_phase_d_replay_decisions_run_id", "phase_d_replay_decisions", ["run_id"])
    op.create_index("ix_phase_d_replay_decisions_bot_id", "phase_d_replay_decisions", ["bot_id"])
    op.create_index("ix_phase_d_replay_decisions_llm_provider", "phase_d_replay_decisions", ["llm_provider"])


def downgrade() -> None:
    op.drop_index("ix_phase_d_replay_decisions_llm_provider", table_name="phase_d_replay_decisions")
    op.drop_index("ix_phase_d_replay_decisions_bot_id", table_name="phase_d_replay_decisions")
    op.drop_index("ix_phase_d_replay_decisions_run_id", table_name="phase_d_replay_decisions")
    op.drop_table("phase_d_replay_decisions")
    op.drop_table("phase_d_replay_runs")
    op.drop_index("ix_rag_chunks_content", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_document_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_index("ix_rag_documents_ticker_form", table_name="rag_documents")
    op.drop_index("ix_rag_documents_content_hash", table_name="rag_documents")
    op.drop_index("ix_rag_documents_ticker", table_name="rag_documents")
    op.drop_table("rag_documents")
    op.drop_index("ix_bot_decisions_bot_id", table_name="bot_decisions")
    op.drop_table("bot_decisions")
