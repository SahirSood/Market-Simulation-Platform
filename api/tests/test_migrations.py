import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_alembic_upgrade_head_creates_core_tables(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "migration.db"
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(cfg, "head")

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    tables = set(inspector.get_table_names())
    assert {
        "bot_decisions",
        "rag_documents",
        "rag_chunks",
        "rag_job_status",
        "phase_d_replay_runs",
        "phase_d_replay_decisions",
        "phase_g_audit_events",
        "execution_orders",
        "execution_fills",
        "agent_activity_events",
        "site_analytics_events",
    }.issubset(tables)

    bot_decision_columns = {
        column["name"]
        for column in inspector.get_columns("bot_decisions")
    }
    assert {
        "llm_call_made",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_total_tokens",
        "llm_estimated_cost_usd",
        "model_metadata",
    }.issubset(bot_decision_columns)

    activity_columns = {
        column["name"]
        for column in inspector.get_columns("agent_activity_events")
    }
    assert {
        "bot_id",
        "event_type",
        "stage",
        "tool_name",
        "status",
        "summary",
        "duration_ms",
        "evidence_ids",
        "metadata_json",
    }.issubset(activity_columns)

    analytics_columns = {
        column["name"]
        for column in inspector.get_columns("site_analytics_events")
    }
    assert {
        "event_type",
        "path",
        "referrer_domain",
        "source",
        "utm_source",
        "utm_campaign",
        "target_url",
        "target_domain",
        "session_id",
        "ip_hash",
        "geo_country",
        "geo_country_code",
        "geo_region",
        "geo_city",
        "geo_timezone",
        "geo_org",
        "geo_latitude",
        "geo_longitude",
        "geo_source",
    }.issubset(analytics_columns)
