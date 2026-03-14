"""
ReasoningLog — persists every bot decision to PostgreSQL via SQLAlchemy 2.x.

Each row stores the full decision context (action, ticker, reasoning, headline)
plus a portfolio snapshot so any moment in the simulation can be reconstructed.
Fill summary columns let the UI show "filled X shares at avg $Y" without joins.

Never raises: DB failures are logged and fall back to a local JSONL file.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine,
    String, Float, Integer, Text, DateTime,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON  # fallback for SQLite in tests

from config import DATABASE_URL

logger = logging.getLogger(__name__)

_FALLBACK_FILE = Path("decisions_fallback.jsonl")


class Base(DeclarativeBase):
    pass


class DecisionRecord(Base):
    """
    One row per bot decision cycle.
    portfolio_snapshot is JSONB in Postgres, JSON in SQLite (for tests).
    """
    __tablename__ = "bot_decisions"

    id:             Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    bot_id:         Mapped[str]            = mapped_column(String(64),  nullable=False, index=True)
    bot_name:       Mapped[str]            = mapped_column(String(64),  nullable=False)
    action:         Mapped[str]            = mapped_column(String(8),   nullable=False)   # BUY|SELL|HOLD
    ticker:         Mapped[str | None]     = mapped_column(String(16),  nullable=True)
    quantity:       Mapped[int | None]     = mapped_column(Integer,     nullable=True)
    limit_price:    Mapped[float | None]   = mapped_column(Float,       nullable=True)
    reasoning:      Mapped[str]            = mapped_column(Text,        nullable=False)
    headline_used:  Mapped[str | None]     = mapped_column(Text,        nullable=True)
    llm_provider:   Mapped[str]            = mapped_column(String(32),  nullable=False)
    fill_count:     Mapped[int]            = mapped_column(Integer,     default=0)
    fill_qty_total: Mapped[int]            = mapped_column(Integer,     default=0)
    fill_avg_price: Mapped[float | None]   = mapped_column(Float,       nullable=True)
    # Use JSON (works for both Postgres JSONB and SQLite) — SQLAlchemy maps to JSONB on PG
    portfolio_snapshot: Mapped[dict]       = mapped_column(JSON,        nullable=False)


class ReasoningLog:
    def __init__(self, database_url: str = None, echo: bool = False):
        url = database_url or DATABASE_URL
        if not url:
            raise ValueError(
                "DATABASE_URL not set. Add it to .env or pass database_url= explicitly."
            )
        self._engine = create_engine(
            url, echo=echo,
            # pool_size / max_overflow only valid for non-SQLite drivers
            **({} if url.startswith("sqlite") else {"pool_size": 5, "max_overflow": 2}),
        )
        Base.metadata.create_all(self._engine)
        logger.info(f"[ReasoningLog] Connected to {url.split('@')[-1]}")  # hide credentials

    # ── Write ──────────────────────────────────────────────────────────────────

    def log(self, bot, decision, fills: list) -> None:
        """
        Persist one decision. Never raises — failures go to the fallback JSONL file.
        """
        fill_qty_total = sum(f.quantity for f in fills)
        fill_avg_price = (
            sum(f.price * f.quantity for f in fills) / fill_qty_total
            if fill_qty_total > 0 else None
        )

        record_dict = {
            "timestamp":           datetime.now(timezone.utc).isoformat(),
            "bot_id":              bot.bot_id,
            "bot_name":            bot.name,
            "action":              decision.action,
            "ticker":              decision.ticker,
            "quantity":            decision.quantity,
            "limit_price":         decision.limit_price,
            "reasoning":           decision.reasoning,
            "headline_used":       decision.headline_used,
            "llm_provider":        bot.llm_provider,
            "fill_count":          len(fills),
            "fill_qty_total":      fill_qty_total,
            "fill_avg_price":      fill_avg_price,
            "portfolio_snapshot":  bot.portfolio.snapshot(),
        }

        try:
            record = DecisionRecord(
                timestamp          = datetime.now(timezone.utc),
                bot_id             = bot.bot_id,
                bot_name           = bot.name,
                action             = decision.action,
                ticker             = decision.ticker,
                quantity           = decision.quantity,
                limit_price        = decision.limit_price,
                reasoning          = decision.reasoning,
                headline_used      = decision.headline_used,
                llm_provider       = bot.llm_provider,
                fill_count         = len(fills),
                fill_qty_total     = fill_qty_total,
                fill_avg_price     = fill_avg_price,
                portfolio_snapshot = bot.portfolio.snapshot(),
            )
            with Session(self._engine) as session:
                session.add(record)
                session.commit()

        except Exception as e:
            logger.error(f"[ReasoningLog] DB write failed for {bot.bot_id}: {e}")
            self._write_fallback(record_dict)

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_decisions(
        self,
        bot_id: str = None,
        action: str = None,
        limit:  int = 100,
    ) -> list[DecisionRecord]:
        """Return recent decisions, newest first. Optionally filter by bot_id or action."""
        with Session(self._engine) as session:
            q = session.query(DecisionRecord).order_by(
                DecisionRecord.timestamp.desc()
            )
            if bot_id:
                q = q.filter(DecisionRecord.bot_id == bot_id)
            if action:
                q = q.filter(DecisionRecord.action == action)
            return q.limit(limit).all()

    # ── Fallback ───────────────────────────────────────────────────────────────

    def _write_fallback(self, record_dict: dict) -> None:
        """Append one JSON line to the fallback file when the DB is unavailable."""
        try:
            with _FALLBACK_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record_dict) + "\n")
            logger.info(f"[ReasoningLog] Written to fallback file: {_FALLBACK_FILE}")
        except Exception as e:
            logger.critical(f"[ReasoningLog] Fallback file write also failed: {e}")
