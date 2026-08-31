"""Apply or reconcile the production Alembic schema before an API deploy."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]

# Older hosted instances used SQLAlchemy metadata.create_all() during startup,
# so their tables can be current even when alembic_version still reports 0003.
# These columns/tables cover every migration after that bootstrap revision.
REQUIRED_SCHEMA = {
    "bot_decisions": {
        "llm_call_made",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_total_tokens",
        "llm_estimated_cost_usd",
        "hold_cause",
    },
    "phase_d_replay_decisions": {
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_total_tokens",
        "llm_estimated_cost_usd",
        "hold_cause",
    },
    "site_analytics_events": {
        "geo_country",
        "geo_country_code",
        "geo_region",
        "geo_city",
        "geo_timezone",
        "geo_continent",
        "geo_org",
        "geo_asn",
        "geo_latitude",
        "geo_longitude",
        "geo_source",
    },
    "execution_orders": set(),
    "execution_fills": set(),
    "agent_activity_events": set(),
    "decision_outcomes": set(),
}


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def _schema_is_current(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        for table, required_columns in REQUIRED_SCHEMA.items():
            if table not in tables:
                return False
            if required_columns:
                columns = {column["name"] for column in inspector.get_columns(table)}
                if not required_columns.issubset(columns):
                    return False
        return True
    finally:
        engine.dispose()


def _bootstrap_current_models(database_url: str) -> None:
    """Repair an ORM-created legacy schema before recording its Alembic head."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    simulator = ROOT / "simulator"
    if str(simulator) not in sys.path:
        sys.path.insert(0, str(simulator))

    # These constructors already own the project's forward-compatible
    # create/optional-column behavior; keeping it here avoids duplicating DDL.
    from audit import AuditLog
    from rag.repository import RagRepository
    from reasoning_log import ReasoningLog
    from replay import ReplayStore
    from site_analytics import SiteAnalyticsStore

    ReasoningLog(database_url)
    ReplayStore(database_url)
    repository = RagRepository(database_url)
    repository.create_tables()
    AuditLog(database_url)
    SiteAnalyticsStore(database_url)


def prepare(database_url: str | None = None) -> str:
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for production migrations")

    config = _alembic_config()
    try:
        if _schema_is_current(url):
            command.stamp(config, "head")
            return "stamped_existing_schema"

        command.upgrade(config, "head")
        return "upgraded_schema"
    except Exception as migration_error:
        # A pre-migration release may have created the current tables with
        # metadata.create_all() but left Alembic at an older revision. Rebuild
        # only the current model shape, verify it, then reconcile the marker.
        _bootstrap_current_models(url)
        if not _schema_is_current(url):
            raise migration_error
        command.stamp(config, "head")
        return "reconciled_existing_schema"


if __name__ == "__main__":
    result = prepare()
    print({"status": "ok", "result": result})
