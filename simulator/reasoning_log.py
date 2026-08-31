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
    UniqueConstraint, create_engine,
    String, Float, Integer, Text, DateTime, Boolean, ForeignKey, inspect, text, func,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON  # fallback for SQLite in tests

from config import BENCHMARK_TICKERS, DATABASE_URL
from model_config import bot_model_metadata

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
    hold_cause:     Mapped[str | None]     = mapped_column(String(32),  nullable=True, index=True)
    ticker:         Mapped[str | None]     = mapped_column(String(16),  nullable=True)
    quantity:       Mapped[int | None]     = mapped_column(Integer,     nullable=True)
    limit_price:    Mapped[float | None]   = mapped_column(Float,       nullable=True)
    reasoning:      Mapped[str]            = mapped_column(Text,        nullable=False)
    headline_used:  Mapped[str | None]     = mapped_column(Text,        nullable=True)
    confidence:     Mapped[float | None]   = mapped_column(Float,       nullable=True)
    evidence_ids:   Mapped[list]           = mapped_column(JSON,        default=list)
    evidence_urls:  Mapped[list]           = mapped_column(JSON,        default=list)
    speculative:    Mapped[bool]           = mapped_column(Boolean,     default=False)
    llm_call_made:   Mapped[bool | None]    = mapped_column(Boolean,     default=True, nullable=True)
    llm_input_tokens: Mapped[int | None]     = mapped_column(Integer,     nullable=True)
    llm_output_tokens: Mapped[int | None]    = mapped_column(Integer,     nullable=True)
    llm_total_tokens: Mapped[int | None]     = mapped_column(Integer,     nullable=True)
    llm_estimated_cost_usd: Mapped[float | None] = mapped_column(Float,   nullable=True)
    llm_provider:   Mapped[str]            = mapped_column(String(32),  nullable=False)
    fill_count:     Mapped[int]            = mapped_column(Integer,     default=0)
    fill_qty_total: Mapped[int]            = mapped_column(Integer,     default=0)
    fill_avg_price: Mapped[float | None]   = mapped_column(Float,       nullable=True)
    model_metadata: Mapped[dict]           = mapped_column(JSON,        nullable=False, default=dict)
    # Use JSON (works for both Postgres JSONB and SQLite) — SQLAlchemy maps to JSONB on PG
    portfolio_snapshot: Mapped[dict]       = mapped_column(JSON,        nullable=False)


class ExecutionOrderRecord(Base):
    """Durable ledger row for every non-HOLD order attempt."""
    __tablename__ = "execution_orders"

    id:              Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp:       Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    decision_id:     Mapped[int | None]     = mapped_column(ForeignKey("bot_decisions.id"), nullable=True, index=True)
    bot_id:          Mapped[str]            = mapped_column(String(64), nullable=False, index=True)
    bot_name:        Mapped[str]            = mapped_column(String(64), nullable=False)
    llm_provider:    Mapped[str]            = mapped_column(String(32), nullable=False)
    engine_order_id: Mapped[int | None]     = mapped_column(Integer, nullable=True, index=True)
    action:          Mapped[str]            = mapped_column(String(8), nullable=False)
    ticker:          Mapped[str | None]     = mapped_column(String(16), nullable=True, index=True)
    order_type:      Mapped[str | None]     = mapped_column(String(16), nullable=True)
    quantity:        Mapped[int | None]     = mapped_column(Integer, nullable=True)
    submitted_price: Mapped[float | None]   = mapped_column(Float, nullable=True)
    limit_price:     Mapped[float | None]   = mapped_column(Float, nullable=True)
    status:          Mapped[str]            = mapped_column(String(32), nullable=False, index=True)
    rejection_reason: Mapped[str | None]    = mapped_column(Text, nullable=True)
    fill_count:      Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    fill_qty_total:  Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    fill_avg_price:  Mapped[float | None]   = mapped_column(Float, nullable=True)
    reasoning:       Mapped[str]            = mapped_column(Text, nullable=False)
    portfolio_snapshot: Mapped[dict]        = mapped_column(JSON, nullable=False)


class ExecutionFillRecord(Base):
    """One row per fill, replayable into portfolio state after API restarts."""
    __tablename__ = "execution_fills"

    id:                  Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_order_id:  Mapped[int]        = mapped_column(ForeignKey("execution_orders.id"), nullable=False, index=True)
    engine_order_id:     Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    timestamp:           Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False)
    bot_id:              Mapped[str]        = mapped_column(String(64), nullable=False, index=True)
    ticker:              Mapped[str]        = mapped_column(String(16), nullable=False, index=True)
    side:                Mapped[str]        = mapped_column(String(8), nullable=False)
    quantity:            Mapped[int]        = mapped_column(Integer, nullable=False)
    price:               Mapped[float]      = mapped_column(Float, nullable=False)
    notional:            Mapped[float]      = mapped_column(Float, nullable=False)


class AgentActivityRecord(Base):
    """Compact public-safe trace of agent, tool, risk, and execution stages."""
    __tablename__ = "agent_activity_events"

    id:             Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp:      Mapped[datetime]        = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    decision_id:    Mapped[int | None]      = mapped_column(ForeignKey("bot_decisions.id"), nullable=True, index=True)
    bot_id:         Mapped[str | None]      = mapped_column(String(64), nullable=True, index=True)
    bot_name:       Mapped[str | None]      = mapped_column(String(64), nullable=True)
    llm_provider:   Mapped[str | None]      = mapped_column(String(32), nullable=True, index=True)
    event_type:     Mapped[str]             = mapped_column(String(32), nullable=False, index=True)
    stage:          Mapped[str]             = mapped_column(String(64), nullable=False, index=True)
    tool_name:      Mapped[str | None]      = mapped_column(String(64), nullable=True, index=True)
    status:         Mapped[str]             = mapped_column(String(32), nullable=False, index=True)
    summary:        Mapped[str]             = mapped_column(Text, nullable=False)
    duration_ms:    Mapped[float | None]    = mapped_column(Float, nullable=True)
    evidence_ids:   Mapped[list]            = mapped_column(JSON, default=list, nullable=False)
    metadata_json:  Mapped[dict]            = mapped_column(JSON, default=dict, nullable=False)


class DecisionOutcomeRecord(Base):
    """Immediate and future labels for a logged bot decision."""
    __tablename__ = "decision_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "horizon",
            name="uq_decision_outcomes_decision_horizon",
        ),
    )

    id:             Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id:    Mapped[int]             = mapped_column(ForeignKey("bot_decisions.id"), nullable=False, index=True)
    bot_id:         Mapped[str]             = mapped_column(String(64), nullable=False, index=True)
    bot_name:       Mapped[str]             = mapped_column(String(64), nullable=False)
    llm_provider:   Mapped[str]             = mapped_column(String(32), nullable=False, index=True)
    decision_timestamp: Mapped[datetime]    = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    horizon:        Mapped[str]             = mapped_column(String(16), nullable=False, index=True)
    horizon_seconds: Mapped[int]            = mapped_column(Integer, nullable=False)
    observed_at:    Mapped[datetime]        = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    action:         Mapped[str]             = mapped_column(String(8), nullable=False)
    ticker:         Mapped[str | None]      = mapped_column(String(16), nullable=True, index=True)
    quantity:       Mapped[int | None]      = mapped_column(Integer, nullable=True)
    entry_price:    Mapped[float | None]    = mapped_column(Float, nullable=True)
    mark_price:     Mapped[float | None]    = mapped_column(Float, nullable=True)
    portfolio_value_at_decision: Mapped[float | None] = mapped_column(Float, nullable=True)
    portfolio_value_at_observation: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_pnl:   Mapped[float | None]    = mapped_column(Float, nullable=True)
    portfolio_delta: Mapped[float | None]   = mapped_column(Float, nullable=True)
    llm_estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_after_llm_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_quantity: Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    risk_approved:  Mapped[bool | None]     = mapped_column(Boolean, nullable=True)
    outcome_status: Mapped[str]             = mapped_column(String(32), nullable=False, index=True)
    metadata_json:  Mapped[dict]            = mapped_column(JSON, default=dict, nullable=False)


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
            **({} if url.startswith("sqlite") else {
                "pool_size": 5,
                "max_overflow": 2,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
            }),
        )
        Base.metadata.create_all(self._engine)
        self._ensure_optional_columns()
        logger.info(f"[ReasoningLog] Connected to {url.split('@')[-1]}")  # hide credentials

    def _ensure_optional_columns(self) -> None:
        inspector = inspect(self._engine)
        if "bot_decisions" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("bot_decisions")}
        if "model_metadata" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN model_metadata JSON"))
        if "llm_call_made" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN llm_call_made BOOLEAN"))
        if "llm_input_tokens" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN llm_input_tokens INTEGER"))
        if "llm_output_tokens" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN llm_output_tokens INTEGER"))
        if "llm_total_tokens" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN llm_total_tokens INTEGER"))
        if "llm_estimated_cost_usd" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN llm_estimated_cost_usd FLOAT"))
        if "hold_cause" not in columns:
            with self._engine.begin() as conn:
                conn.execute(text("ALTER TABLE bot_decisions ADD COLUMN hold_cause VARCHAR(32)"))

    # ── Write ──────────────────────────────────────────────────────────────────

    def log(self, bot, decision, fills: list) -> int | None:
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
            total_value = bot.portfolio.mark_to_market(bot.price_feed)
            snapshot["total_value"] = round(float(total_value), 2)
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

        llm_call_made = bool(getattr(decision, "llm_call_made", True))
        llm_estimated_cost_usd = (
            float(getattr(decision, "llm_estimated_cost_usd", 0.0) or 0.0)
            if llm_call_made
            else 0.0
        )

        record_dict = {
            "timestamp":           datetime.now(timezone.utc).isoformat(),
            "bot_id":              bot.bot_id,
            "bot_name":            bot.name,
            "action":              decision.action,
            "hold_cause":          getattr(decision, "hold_cause", None),
            "ticker":              decision.ticker,
            "quantity":            decision.quantity,
            "limit_price":         decision.limit_price,
            "reasoning":           decision.reasoning,
            "headline_used":       decision.headline_used,
            "confidence":          decision.confidence,
            "evidence_ids":        decision.evidence_ids,
            "evidence_urls":       decision.evidence_urls,
            "speculative":         decision.speculative,
            "llm_call_made":       llm_call_made,
            "llm_input_tokens":     getattr(decision, "llm_input_tokens", None),
            "llm_output_tokens":    getattr(decision, "llm_output_tokens", None),
            "llm_total_tokens":     getattr(decision, "llm_total_tokens", None),
            "llm_estimated_cost_usd": llm_estimated_cost_usd,
            "llm_provider":        bot.llm_provider,
            "model_metadata":      bot_model_metadata(bot, getattr(bot, "risk_limits", None)),
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
                hold_cause         = getattr(decision, "hold_cause", None),
                ticker             = decision.ticker,
                quantity           = decision.quantity,
                limit_price        = decision.limit_price,
                reasoning          = decision.reasoning,
                headline_used      = decision.headline_used,
                confidence         = decision.confidence,
                evidence_ids       = decision.evidence_ids,
                evidence_urls      = decision.evidence_urls,
                speculative        = decision.speculative,
                llm_call_made      = llm_call_made,
                llm_input_tokens    = getattr(decision, "llm_input_tokens", None),
                llm_output_tokens   = getattr(decision, "llm_output_tokens", None),
                llm_total_tokens    = getattr(decision, "llm_total_tokens", None),
                llm_estimated_cost_usd = llm_estimated_cost_usd,
                llm_provider       = bot.llm_provider,
                model_metadata     = bot_model_metadata(bot, getattr(bot, "risk_limits", None)),
                fill_count         = len(fills),
                fill_qty_total     = fill_qty_total,
                fill_avg_price     = fill_avg_price,
                portfolio_snapshot = snapshot,
            )
            with Session(self._engine) as session:
                session.add(record)
                session.flush()
                record_id = int(record.id)
                session.commit()
                return record_id

        except Exception as e:
            logger.error(f"[ReasoningLog] DB write failed for {bot.bot_id}: {e}")
            self._write_fallback(record_dict)
            return None

    # ── Read ───────────────────────────────────────────────────────────────────

    def record_execution_order(
        self,
        bot,
        decision,
        engine_order_id: int | None,
        order_type: str | None,
        submitted_price: float | None,
        fills: list,
        decision_id: int | None = None,
        status: str | None = None,
        rejection_reason: str | None = None,
    ) -> int | None:
        """
        Persist the execution outcome for a non-HOLD order attempt. Never raises.
        """
        fill_qty_total = sum(int(getattr(f, "quantity", 0) or 0) for f in fills)
        fill_notional = sum(
            float(getattr(f, "price", 0.0) or 0.0) * int(getattr(f, "quantity", 0) or 0)
            for f in fills
        )
        fill_avg_price = fill_notional / fill_qty_total if fill_qty_total > 0 else None
        resolved_status = status or self._execution_status(
            decision=decision,
            engine_order_id=engine_order_id,
            order_type=order_type,
            fill_qty_total=fill_qty_total,
            rejection_reason=rejection_reason,
        )
        snapshot = bot.portfolio.snapshot()

        record_dict = {
            "record_type": "execution_order",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": decision_id,
            "bot_id": bot.bot_id,
            "bot_name": bot.name,
            "llm_provider": bot.llm_provider,
            "engine_order_id": engine_order_id,
            "action": getattr(decision, "action", None),
            "ticker": getattr(decision, "ticker", None),
            "order_type": order_type,
            "quantity": getattr(decision, "quantity", None),
            "submitted_price": submitted_price,
            "limit_price": getattr(decision, "limit_price", None),
            "status": resolved_status,
            "rejection_reason": rejection_reason,
            "fill_count": len(fills),
            "fill_qty_total": fill_qty_total,
            "fill_avg_price": fill_avg_price,
            "reasoning": getattr(decision, "reasoning", ""),
            "portfolio_snapshot": snapshot,
            "fills": [
                {
                    "engine_order_id": getattr(fill, "order_id", engine_order_id),
                    "timestamp": _fill_timestamp(fill).isoformat(),
                    "ticker": getattr(fill, "ticker", None),
                    "side": getattr(fill, "side", None),
                    "quantity": getattr(fill, "quantity", None),
                    "price": getattr(fill, "price", None),
                }
                for fill in fills
            ],
        }

        try:
            order = ExecutionOrderRecord(
                timestamp=datetime.now(timezone.utc),
                decision_id=decision_id,
                bot_id=bot.bot_id,
                bot_name=bot.name,
                llm_provider=bot.llm_provider,
                engine_order_id=engine_order_id,
                action=str(getattr(decision, "action", "") or "").upper(),
                ticker=str(getattr(decision, "ticker", "") or "").upper() or None,
                order_type=str(order_type).upper() if order_type else None,
                quantity=getattr(decision, "quantity", None),
                submitted_price=submitted_price,
                limit_price=getattr(decision, "limit_price", None),
                status=resolved_status,
                rejection_reason=rejection_reason,
                fill_count=len(fills),
                fill_qty_total=fill_qty_total,
                fill_avg_price=fill_avg_price,
                reasoning=getattr(decision, "reasoning", ""),
                portfolio_snapshot=snapshot,
            )
            with Session(self._engine) as session:
                session.add(order)
                session.flush()
                order_record_id = int(order.id)
                for fill in fills:
                    quantity = int(getattr(fill, "quantity", 0) or 0)
                    price = float(getattr(fill, "price", 0.0) or 0.0)
                    session.add(ExecutionFillRecord(
                        execution_order_id=order_record_id,
                        engine_order_id=getattr(fill, "order_id", engine_order_id),
                        timestamp=_fill_timestamp(fill),
                        bot_id=bot.bot_id,
                        ticker=str(getattr(fill, "ticker", "") or "").upper(),
                        side=str(getattr(fill, "side", "") or "").upper(),
                        quantity=quantity,
                        price=price,
                        notional=round(quantity * price, 8),
                    ))
                session.commit()
                return order_record_id
        except Exception as e:
            logger.error(f"[ReasoningLog] Execution ledger write failed for {bot.bot_id}: {e}")
            self._write_fallback(record_dict)
            return None

    def record_passive_fills(self, bot, fills: list) -> int:
        """Attach later fills to their original resting execution orders."""
        if not fills:
            return 0
        recorded = 0
        try:
            snapshot = bot.portfolio.snapshot()
            with Session(self._engine) as session:
                for fill in fills:
                    engine_order_id = getattr(fill, "order_id", None)
                    order = (
                        session.query(ExecutionOrderRecord)
                        .filter(
                            ExecutionOrderRecord.bot_id == bot.bot_id,
                            ExecutionOrderRecord.engine_order_id == engine_order_id,
                        )
                        .order_by(ExecutionOrderRecord.id.desc())
                        .first()
                    )
                    if order is None:
                        logger.warning(
                            "[ReasoningLog] No execution order found for passive fill %s/%s",
                            bot.bot_id,
                            engine_order_id,
                        )
                        continue

                    quantity = int(getattr(fill, "quantity", 0) or 0)
                    price = float(getattr(fill, "price", 0.0) or 0.0)
                    if quantity <= 0 or price < 0:
                        continue
                    previous_qty = int(order.fill_qty_total or 0)
                    previous_notional = float(order.fill_avg_price or 0.0) * previous_qty
                    new_qty = previous_qty + quantity
                    new_avg = (previous_notional + price * quantity) / new_qty

                    session.add(ExecutionFillRecord(
                        execution_order_id=int(order.id),
                        engine_order_id=engine_order_id,
                        timestamp=_fill_timestamp(fill),
                        bot_id=bot.bot_id,
                        ticker=str(getattr(fill, "ticker", "") or "").upper(),
                        side=str(getattr(fill, "side", "") or "").upper(),
                        quantity=quantity,
                        price=price,
                        notional=round(quantity * price, 8),
                    ))
                    order.fill_count = int(order.fill_count or 0) + 1
                    order.fill_qty_total = new_qty
                    order.fill_avg_price = new_avg
                    order.portfolio_snapshot = snapshot
                    requested_qty = int(order.quantity or 0)
                    order.status = (
                        "FILLED"
                        if requested_qty <= 0 or new_qty >= requested_qty
                        else "PARTIALLY_FILLED"
                    )

                    if order.decision_id is not None:
                        decision = session.get(DecisionRecord, int(order.decision_id))
                        if decision is not None:
                            decision_qty = int(decision.fill_qty_total or 0)
                            decision_notional = float(decision.fill_avg_price or 0.0) * decision_qty
                            total_decision_qty = decision_qty + quantity
                            decision.fill_count = int(decision.fill_count or 0) + 1
                            decision.fill_qty_total = total_decision_qty
                            decision.fill_avg_price = (
                                decision_notional + price * quantity
                            ) / total_decision_qty
                            decision.portfolio_snapshot = snapshot
                    recorded += 1
                session.commit()
            return recorded
        except Exception as exc:
            logger.error("[ReasoningLog] Passive fill ledger write failed for %s: %s", bot.bot_id, exc)
            return 0

    def record_agent_activity(
        self,
        *,
        bot=None,
        bot_id: str | None = None,
        bot_name: str | None = None,
        llm_provider: str | None = None,
        event_type: str,
        stage: str,
        status: str,
        summary: str,
        tool_name: str | None = None,
        duration_ms: float | None = None,
        decision_id: int | None = None,
        evidence_ids: list | None = None,
        metadata: dict | None = None,
    ) -> int | None:
        """Persist a compact, public-safe agent activity event. Never raises."""
        resolved_bot_id = bot_id or getattr(bot, "bot_id", None)
        resolved_bot_name = bot_name or getattr(bot, "name", None)
        resolved_provider = llm_provider or getattr(bot, "llm_provider", None)
        try:
            record = AgentActivityRecord(
                timestamp=datetime.now(timezone.utc),
                decision_id=decision_id,
                bot_id=resolved_bot_id,
                bot_name=resolved_bot_name,
                llm_provider=str(resolved_provider).lower() if resolved_provider else None,
                event_type=str(event_type or "agent").lower()[:32],
                stage=str(stage or "unknown")[:64],
                tool_name=str(tool_name)[:64] if tool_name else None,
                status=str(status or "unknown").lower()[:32],
                summary=str(summary or "")[:600],
                duration_ms=round(float(duration_ms), 3) if duration_ms is not None else None,
                evidence_ids=_normalize_activity_ids(evidence_ids),
                metadata_json=_json_safe(metadata or {}),
            )
            with Session(self._engine) as session:
                session.add(record)
                session.flush()
                record_id = int(record.id)
                session.commit()
                return record_id
        except Exception as e:
            logger.warning("[ReasoningLog] Agent activity write failed: %s", e)
            return None

    def record_immediate_outcome(
        self,
        *,
        bot,
        decision,
        decision_id: int | None,
        fills: list,
        baseline_snapshot: dict | None,
        risk_approved: bool | None,
        outcome_status: str,
        risk_reason: str | None = None,
    ) -> int | None:
        """Persist the immediate label created during the scheduler cycle."""
        if decision_id is None:
            return None

        action = str(getattr(decision, "action", "HOLD") or "HOLD").upper()
        ticker = _normalize_ticker(getattr(decision, "ticker", None))
        fill_qty_total = sum(int(getattr(fill, "quantity", 0) or 0) for fill in fills)
        fill_notional = sum(
            float(getattr(fill, "price", 0.0) or 0.0) * int(getattr(fill, "quantity", 0) or 0)
            for fill in fills
        )
        entry_price = fill_notional / fill_qty_total if fill_qty_total > 0 else None
        if entry_price is None:
            entry_price = _safe_float(getattr(decision, "limit_price", None))
        mark_price = _mark_price(getattr(bot, "price_feed", None), ticker)
        baseline_value = _portfolio_value(baseline_snapshot or {})
        position_pnl = _position_pnl(
            action=action,
            filled_quantity=fill_qty_total,
            entry_price=entry_price,
            mark_price=mark_price,
        )
        portfolio_delta = position_pnl if position_pnl is not None else 0.0
        observed_value = (
            round(baseline_value + portfolio_delta, 8)
            if baseline_value is not None and portfolio_delta is not None
            else None
        )
        llm_cost = float(getattr(decision, "llm_estimated_cost_usd", 0.0) or 0.0)

        return self.record_decision_outcome(
            decision_id=decision_id,
            bot_id=getattr(bot, "bot_id", "unknown"),
            bot_name=getattr(bot, "name", "unknown"),
            llm_provider=str(getattr(bot, "llm_provider", "unknown") or "unknown").lower(),
            decision_timestamp=datetime.now(timezone.utc),
            horizon="immediate",
            horizon_seconds=0,
            observed_at=datetime.now(timezone.utc),
            action=action,
            ticker=ticker,
            quantity=getattr(decision, "quantity", None),
            entry_price=entry_price,
            mark_price=mark_price,
            portfolio_value_at_decision=baseline_value,
            portfolio_value_at_observation=observed_value,
            position_pnl=position_pnl,
            portfolio_delta=portfolio_delta,
            llm_estimated_cost_usd=llm_cost,
            net_after_llm_cost=round(portfolio_delta - llm_cost, 8),
            filled_quantity=fill_qty_total,
            risk_approved=risk_approved,
            outcome_status=outcome_status,
            metadata={
                "source": "scheduler_immediate",
                "fill_count": len(fills),
                "risk_reason": risk_reason,
                "hold_cause": getattr(decision, "hold_cause", None),
                "benchmark_prices_at_decision": _benchmark_prices(
                    getattr(bot, "price_feed", None)
                ),
            },
        )

    def record_decision_outcome(self, **payload) -> int | None:
        """Persist one decision outcome label. Never raises."""
        try:
            record = DecisionOutcomeRecord(
                decision_id=int(payload["decision_id"]),
                bot_id=str(payload.get("bot_id") or "unknown")[:64],
                bot_name=str(payload.get("bot_name") or "unknown")[:64],
                llm_provider=str(payload.get("llm_provider") or "unknown").lower()[:32],
                decision_timestamp=_as_utc_datetime(payload.get("decision_timestamp")),
                horizon=str(payload.get("horizon") or "unknown")[:16],
                horizon_seconds=int(payload.get("horizon_seconds") or 0),
                observed_at=_as_utc_datetime(payload.get("observed_at")),
                action=str(payload.get("action") or "HOLD").upper()[:8],
                ticker=_normalize_ticker(payload.get("ticker")),
                quantity=_safe_int(payload.get("quantity")),
                entry_price=_safe_float(payload.get("entry_price")),
                mark_price=_safe_float(payload.get("mark_price")),
                portfolio_value_at_decision=_safe_float(
                    payload.get("portfolio_value_at_decision")
                ),
                portfolio_value_at_observation=_safe_float(
                    payload.get("portfolio_value_at_observation")
                ),
                position_pnl=_safe_float(payload.get("position_pnl")),
                portfolio_delta=_safe_float(payload.get("portfolio_delta")),
                llm_estimated_cost_usd=_safe_float(
                    payload.get("llm_estimated_cost_usd")
                ),
                net_after_llm_cost=_safe_float(payload.get("net_after_llm_cost")),
                filled_quantity=max(0, _safe_int(payload.get("filled_quantity")) or 0),
                risk_approved=payload.get("risk_approved"),
                outcome_status=str(payload.get("outcome_status") or "unknown").lower()[:32],
                metadata_json=_json_safe(payload.get("metadata") or {}),
            )
            with Session(self._engine) as session:
                session.add(record)
                session.flush()
                record_id = int(record.id)
                session.commit()
                return record_id
        except Exception as e:
            logger.warning("[ReasoningLog] Decision outcome write failed: %s", e)
            return None

    def get_decision_outcomes(
        self,
        bot_id: str = None,
        horizon: str = None,
        status: str = None,
        limit: int = 1000,
        since: "datetime | None" = None,
        before: "datetime | None" = None,
    ) -> list[dict]:
        """Return outcome labels as plain dicts, newest first."""
        with Session(self._engine) as session:
            q = session.query(DecisionOutcomeRecord).order_by(
                DecisionOutcomeRecord.observed_at.desc(),
                DecisionOutcomeRecord.id.desc(),
            )
            if bot_id:
                q = q.filter(DecisionOutcomeRecord.bot_id == bot_id)
            if horizon:
                q = q.filter(DecisionOutcomeRecord.horizon == str(horizon))
            if status:
                q = q.filter(DecisionOutcomeRecord.outcome_status == str(status).lower())
            if since:
                q = q.filter(DecisionOutcomeRecord.observed_at >= since)
            if before:
                q = q.filter(DecisionOutcomeRecord.observed_at < before)
            rows = q.limit(limit).all()
            return [_outcome_to_dict(row) for row in rows]

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
                    "hold_cause":         r.hold_cause,
                    "ticker":             r.ticker,
                    "quantity":           r.quantity,
                    "limit_price":        r.limit_price,
                    "reasoning":          r.reasoning,
                    "headline_used":      r.headline_used,
                    "confidence":         r.confidence,
                    "evidence_ids":       r.evidence_ids,
                    "evidence_urls":      r.evidence_urls,
                    "speculative":        r.speculative,
                    "llm_call_made":      True if r.llm_call_made is None else bool(r.llm_call_made),
                    "llm_input_tokens":    r.llm_input_tokens,
                    "llm_output_tokens":   r.llm_output_tokens,
                    "llm_total_tokens":    r.llm_total_tokens,
                    "llm_estimated_cost_usd": float(r.llm_estimated_cost_usd or 0.0),
                    "llm_provider":       r.llm_provider,
                    "model_metadata":     r.model_metadata or {},
                    "fill_count":         r.fill_count,
                    "fill_qty_total":     r.fill_qty_total,
                    "fill_avg_price":     r.fill_avg_price,
                    "portfolio_snapshot": r.portfolio_snapshot,
                }
                for r in rows
            ]

    # ── Fallback ───────────────────────────────────────────────────────────────

    def get_execution_orders(
        self,
        bot_id: str = None,
        status: str = None,
        limit: int = 100,
        filled_only: bool = False,
    ) -> list[dict]:
        """Return durable execution-order rows as plain dicts, newest first."""
        with Session(self._engine) as session:
            q = session.query(ExecutionOrderRecord).order_by(
                ExecutionOrderRecord.timestamp.desc(),
                ExecutionOrderRecord.id.desc(),
            )
            if bot_id:
                q = q.filter(ExecutionOrderRecord.bot_id == bot_id)
            if status:
                q = q.filter(ExecutionOrderRecord.status == str(status).upper())
            if filled_only:
                q = q.filter(ExecutionOrderRecord.fill_qty_total > 0)
            rows = q.limit(limit).all()
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "decision_id": r.decision_id,
                    "bot_id": r.bot_id,
                    "bot_name": r.bot_name,
                    "llm_provider": r.llm_provider,
                    "engine_order_id": r.engine_order_id,
                    "action": r.action,
                    "ticker": r.ticker,
                    "order_type": r.order_type,
                    "quantity": r.quantity,
                    "submitted_price": r.submitted_price,
                    "limit_price": r.limit_price,
                    "status": r.status,
                    "rejection_reason": r.rejection_reason,
                    "fill_count": r.fill_count,
                    "fill_qty_total": r.fill_qty_total,
                    "fill_avg_price": r.fill_avg_price,
                    "reasoning": r.reasoning,
                    "portfolio_snapshot": r.portfolio_snapshot,
                }
                for r in rows
            ]

    def get_agent_activity(
        self,
        bot_id: str = None,
        limit: int = 100,
        event_type: str = None,
        stage: str = None,
    ) -> list[dict]:
        """Return compact agent activity rows as plain dicts, newest first."""
        with Session(self._engine) as session:
            q = session.query(AgentActivityRecord).order_by(
                AgentActivityRecord.timestamp.desc(),
                AgentActivityRecord.id.desc(),
            )
            if bot_id:
                q = q.filter(AgentActivityRecord.bot_id == bot_id)
            if event_type:
                q = q.filter(AgentActivityRecord.event_type == str(event_type).lower())
            if stage:
                q = q.filter(AgentActivityRecord.stage == str(stage))
            rows = q.limit(limit).all()
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "decision_id": r.decision_id,
                    "bot_id": r.bot_id,
                    "bot_name": r.bot_name,
                    "llm_provider": r.llm_provider,
                    "event_type": r.event_type,
                    "stage": r.stage,
                    "tool_name": r.tool_name,
                    "status": r.status,
                    "summary": r.summary,
                    "duration_ms": r.duration_ms,
                    "evidence_ids": r.evidence_ids or [],
                    "metadata": r.metadata_json or {},
                }
                for r in rows
            ]

    def get_execution_fills(
        self,
        bot_id: str = None,
        limit: int = 5000,
    ) -> list[dict]:
        """Return fill rows oldest first so callers can reconstruct portfolios."""
        with Session(self._engine) as session:
            q = session.query(ExecutionFillRecord).order_by(
                ExecutionFillRecord.timestamp.asc(),
                ExecutionFillRecord.id.asc(),
            )
            if bot_id:
                q = q.filter(ExecutionFillRecord.bot_id == bot_id)
            rows = q.limit(limit).all()
            return [
                {
                    "id": r.id,
                    "execution_order_id": r.execution_order_id,
                    "engine_order_id": r.engine_order_id,
                    "timestamp": r.timestamp,
                    "bot_id": r.bot_id,
                    "ticker": r.ticker,
                    "side": r.side,
                    "quantity": r.quantity,
                    "price": r.price,
                    "notional": r.notional,
                }
                for r in rows
            ]

    def get_filled_decisions(self, bot_id: str, limit: int = 5000) -> list[dict]:
        """
        Return filled decisions oldest-first so live portfolios can be rebuilt
        after a hosted API restart. Decision rows summarize fills by side,
        total quantity, and average price, which is enough to recover holdings.
        """
        with Session(self._engine) as session:
            rows = (
                session.query(DecisionRecord)
                .filter(DecisionRecord.bot_id == bot_id)
                .filter(DecisionRecord.fill_qty_total > 0)
                .filter(DecisionRecord.fill_avg_price.isnot(None))
                .order_by(DecisionRecord.timestamp.asc(), DecisionRecord.id.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "action": r.action,
                    "ticker": r.ticker,
                    "fill_qty_total": r.fill_qty_total,
                    "fill_avg_price": r.fill_avg_price,
                }
                for r in rows
            ]

    def count_decisions(
        self,
        since: "datetime | None" = None,
        before: "datetime | None" = None,
        llm_provider: str | None = None,
        billable_only: bool = False,
    ) -> int:
        """Count decisions, optionally only rows that made a real LLM call."""
        try:
            with Session(self._engine) as session:
                q = session.query(DecisionRecord.id)
                if since:
                    q = q.filter(DecisionRecord.timestamp >= since)
                if before:
                    q = q.filter(DecisionRecord.timestamp < before)
                if llm_provider:
                    q = q.filter(DecisionRecord.llm_provider == str(llm_provider).lower())
                if billable_only:
                    q = q.filter(DecisionRecord.llm_call_made.isnot(False))
                return int(q.count())
        except Exception as e:
            logger.error(f"[ReasoningLog] Count failed: {e}")
            return 0

    def sum_estimated_llm_cost(
        self,
        since: "datetime | None" = None,
        before: "datetime | None" = None,
        llm_provider: str | None = None,
    ) -> float:
        """Sum recorded estimated LLM spend for calls that actually ran."""
        try:
            with Session(self._engine) as session:
                q = session.query(func.coalesce(func.sum(DecisionRecord.llm_estimated_cost_usd), 0.0))
                q = q.filter(DecisionRecord.llm_call_made.isnot(False))
                if since:
                    q = q.filter(DecisionRecord.timestamp >= since)
                if before:
                    q = q.filter(DecisionRecord.timestamp < before)
                if llm_provider:
                    q = q.filter(DecisionRecord.llm_provider == str(llm_provider).lower())
                return float(q.scalar() or 0.0)
        except Exception as e:
            logger.error(f"[ReasoningLog] Cost sum failed: {e}")
            return 0.0

    @staticmethod
    def _execution_status(
        decision,
        engine_order_id: int | None,
        order_type: str | None,
        fill_qty_total: int,
        rejection_reason: str | None,
    ) -> str:
        if rejection_reason or engine_order_id is None:
            return "REJECTED"
        try:
            requested_qty = int(getattr(decision, "quantity", 0) or 0)
        except (TypeError, ValueError):
            requested_qty = 0
        if fill_qty_total > 0 and (requested_qty <= 0 or fill_qty_total >= requested_qty):
            return "FILLED"
        if fill_qty_total > 0:
            return "PARTIALLY_FILLED"
        if str(order_type or "").upper() == "MARKET":
            return "UNFILLED"
        return "OPEN"

    def _write_fallback(self, record_dict: dict) -> None:
        """Append one JSON line to the fallback file when the DB is unavailable."""
        try:
            with _FALLBACK_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record_dict) + "\n")
            logger.info(f"[ReasoningLog] Written to fallback file: {_FALLBACK_FILE}")
        except Exception as e:
            logger.critical(f"[ReasoningLog] Fallback file write also failed: {e}")


def _outcome_to_dict(record: DecisionOutcomeRecord) -> dict:
    return {
        "id": record.id,
        "decision_id": record.decision_id,
        "bot_id": record.bot_id,
        "bot_name": record.bot_name,
        "llm_provider": record.llm_provider,
        "decision_timestamp": record.decision_timestamp,
        "horizon": record.horizon,
        "horizon_seconds": record.horizon_seconds,
        "observed_at": record.observed_at,
        "action": record.action,
        "ticker": record.ticker,
        "quantity": record.quantity,
        "entry_price": record.entry_price,
        "mark_price": record.mark_price,
        "portfolio_value_at_decision": record.portfolio_value_at_decision,
        "portfolio_value_at_observation": record.portfolio_value_at_observation,
        "position_pnl": record.position_pnl,
        "portfolio_delta": record.portfolio_delta,
        "llm_estimated_cost_usd": record.llm_estimated_cost_usd,
        "net_after_llm_cost": record.net_after_llm_cost,
        "filled_quantity": record.filled_quantity,
        "risk_approved": record.risk_approved,
        "outcome_status": record.outcome_status,
        "metadata": record.metadata_json or {},
    }


def _as_utc_datetime(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_ticker(value) -> str | None:
    if value is None:
        return None
    ticker = str(value).upper().strip()
    return ticker if ticker else None


def _portfolio_value(snapshot: dict) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    value = _safe_float(snapshot.get("total_value"))
    if value is not None:
        return round(value, 8)
    cash = _safe_float(snapshot.get("cash"))
    positions = snapshot.get("positions") or {}
    cost_basis = snapshot.get("cost_basis") or {}
    if cash is None or not isinstance(positions, dict):
        return None
    total = cash
    for ticker, quantity in positions.items():
        basis = _safe_float(cost_basis.get(ticker)) or 0.0
        total += basis * int(quantity or 0)
    return round(total, 8)


def _mark_price(price_feed, ticker: str | None) -> float | None:
    if price_feed is None or not ticker:
        return None
    getter = getattr(price_feed, "get_price", None)
    if not callable(getter):
        return None
    try:
        return round(float(getter(ticker)), 8)
    except Exception:
        return None


def _benchmark_prices(price_feed) -> dict[str, float]:
    """Capture benchmark prices alongside the immediate live outcome."""
    prices = {}
    for ticker in BENCHMARK_TICKERS:
        price = _mark_price(price_feed, ticker)
        if price is not None:
            prices[str(ticker).upper()] = price
    return prices


def _position_pnl(
    *,
    action: str,
    filled_quantity: int,
    entry_price: float | None,
    mark_price: float | None,
) -> float | None:
    if entry_price is None or mark_price is None or filled_quantity <= 0:
        return None
    side = str(action or "").upper()
    if side not in {"BUY", "SELL"}:
        return None
    signed_quantity = filled_quantity if side == "BUY" else -filled_quantity
    return round((float(mark_price) - float(entry_price)) * signed_quantity, 8)


def _fill_timestamp(fill) -> datetime:
    value = getattr(fill, "timestamp", None)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), timezone.utc)
    return datetime.now(timezone.utc)


def _normalize_activity_ids(values) -> list[int]:
    if not isinstance(values, list):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        out.append(parsed)
    return out[:20]


def _json_safe(value):
    if isinstance(value, dict):
        return {
            str(key)[:80]: _json_safe(item)
            for key, item in value.items()
            if key is not None
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value[:50]]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value[:50]]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:300]
