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
    String, Float, Integer, Text, DateTime, Boolean,
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
    confidence:     Mapped[float | None]   = mapped_column(Float,       nullable=True)
    evidence_ids:   Mapped[list]           = mapped_column(JSON,        default=list)
    evidence_urls:  Mapped[list]           = mapped_column(JSON,        default=list)
    speculative:    Mapped[bool]           = mapped_column(Boolean,     default=False)
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
        snapshot = bot.portfolio.snapshot()
        try:
            snapshot["total_value"] = round(
                bot.portfolio.mark_to_market(bot.price_feed), 2
            )
        except Exception:
            # Keep persistence robust even if live pricing is temporarily unavailable.
            snapshot["total_value"] = round(
                snapshot.get("cash", 0.0)
                + sum(
                    snapshot.get("cost_basis", {}).get(ticker, 0.0) * quantity
                    for ticker, quantity in snapshot.get("positions", {}).items()
                ),
                2,
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
            "confidence":          decision.confidence,
            "evidence_ids":        decision.evidence_ids,
            "evidence_urls":       decision.evidence_urls,
            "speculative":         decision.speculative,
            "llm_provider":        bot.llm_provider,
            "fill_count":          len(fills),
            "fill_qty_total":      fill_qty_total,
            "fill_avg_price":      fill_avg_price,
            "portfolio_snapshot":  snapshot,
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
                confidence         = decision.confidence,
                evidence_ids       = decision.evidence_ids,
                evidence_urls      = decision.evidence_urls,
                speculative        = decision.speculative,
                llm_provider       = bot.llm_provider,
                fill_count         = len(fills),
                fill_qty_total     = fill_qty_total,
                fill_avg_price     = fill_avg_price,
                portfolio_snapshot = snapshot,
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
        since:  "datetime | None" = None,
        before: "datetime | None" = None,
    ) -> list[dict]:
        """
        Return recent decisions as plain dicts (newest first).
        Returns dicts (not ORM objects) to avoid DetachedInstanceError in the API layer.
        """
        with Session(self._engine) as session:
            q = session.query(DecisionRecord).order_by(
                DecisionRecord.timestamp.desc()
            )
            if bot_id:
                q = q.filter(DecisionRecord.bot_id == bot_id)
            if action:
                q = q.filter(DecisionRecord.action == action)
            if since:
                q = q.filter(DecisionRecord.timestamp >= since)
            if before:
                q = q.filter(DecisionRecord.timestamp < before)
            rows = q.limit(limit).all()
            return [
                {
                    "id":                 r.id,
                    "timestamp":          r.timestamp,
                    "bot_id":             r.bot_id,
                    "bot_name":           r.bot_name,
                    "action":             r.action,
                    "ticker":             r.ticker,
                    "quantity":           r.quantity,
                    "limit_price":        r.limit_price,
                    "reasoning":          r.reasoning,
                    "headline_used":      r.headline_used,
                    "confidence":         r.confidence,
                    "evidence_ids":       r.evidence_ids,
                    "evidence_urls":      r.evidence_urls,
                    "speculative":        r.speculative,
                    "llm_provider":       r.llm_provider,
                    "fill_count":         r.fill_count,
                    "fill_qty_total":     r.fill_qty_total,
                    "fill_avg_price":     r.fill_avg_price,
                    "portfolio_snapshot": r.portfolio_snapshot,
                }
                for r in rows
            ]

    # ── Fallback ───────────────────────────────────────────────────────────────

    def _write_fallback(self, record_dict: dict) -> None:
        """Append one JSON line to the fallback file when the DB is unavailable."""
        try:
            with _FALLBACK_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record_dict) + "\n")
            logger.info(f"[ReasoningLog] Written to fallback file: {_FALLBACK_FILE}")
        except Exception as e:
            logger.critical(f"[ReasoningLog] Fallback file write also failed: {e}")
