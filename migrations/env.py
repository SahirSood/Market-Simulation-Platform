from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from reasoning_log import Base as ReasoningBase  # noqa: E402
from rag.models import Base as RagBase  # noqa: E402
from replay import ReplayBase  # noqa: E402
from audit import AuditBase  # noqa: E402
from site_analytics import SiteAnalyticsBase  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = [
    ReasoningBase.metadata,
    RagBase.metadata,
    ReplayBase.metadata,
    AuditBase.metadata,
    SiteAnalyticsBase.metadata,
]


def _database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured and configured != "sqlite:///marketsim.db":
        return configured
    return os.getenv("DATABASE_URL") or configured


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
