"""Phase D historical replay storage and no-lookahead helpers."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy import JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from model_config import bot_model_metadata
from config import (
    SEED_LIQUIDITY_LEVELS,
    SEED_LIQUIDITY_QTY,
    SEED_LIQUIDITY_SPREAD_PCT,
)
from risk import RiskLimits, risk_check_order


ReplayBase = declarative_base()


class ReplayRunRecord(ReplayBase):
    __tablename__ = "phase_d_replay_runs"

    id = Column(String(36), primary_key=True)
    name = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    input_fingerprint = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)

    decisions = relationship(
        "ReplayDecisionRecord",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ReplayDecisionRecord(ReplayBase):
    __tablename__ = "phase_d_replay_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("phase_d_replay_runs.id"), nullable=False, index=True)
    event_index = Column(Integer, nullable=False)
    as_of_time = Column(DateTime(timezone=True), nullable=False)
    bot_id = Column(String(64), nullable=False, index=True)
    bot_name = Column(String(64), nullable=False)
    llm_provider = Column(String(32), nullable=False, index=True)
    action = Column(String(8), nullable=False)
    hold_cause = Column(String(32), nullable=True)
    ticker = Column(String(16), nullable=True)
    quantity = Column(Integer, nullable=True)
    limit_price = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=False)
    headline_used = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    llm_input_tokens = Column(Integer, nullable=True)
    llm_output_tokens = Column(Integer, nullable=True)
    llm_total_tokens = Column(Integer, nullable=True)
    llm_estimated_cost_usd = Column(Float, nullable=True)
    evidence_ids = Column(JSON, nullable=False, default=list)
    evidence_urls = Column(JSON, nullable=False, default=list)
    speculative = Column(String(8), nullable=False, default="false")
    risk_approved = Column(Boolean, nullable=True)
    risk_reason = Column(Text, nullable=True)
    order_id = Column(Integer, nullable=True)
    fill_count = Column(Integer, nullable=False, default=0)
    fill_qty_total = Column(Integer, nullable=False, default=0)
    fill_avg_price = Column(Float, nullable=True)
    model_metadata = Column(JSON, nullable=False, default=dict)
    portfolio_snapshot = Column(JSON, nullable=False, default=dict)
    event_payload = Column(JSON, nullable=False, default=dict)

    run = relationship("ReplayRunRecord", back_populates="decisions")


class ReplayStore:
    """Small SQL store for fair replay/model-comparison run metadata."""

    def __init__(self, database_url: str = "sqlite:///:memory:", echo: bool = False):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            echo=echo,
            **(
                {}
                if database_url.startswith("sqlite")
                else {"pool_size": 5, "max_overflow": 2, "pool_pre_ping": True}
            ),
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.create_tables()

    def create_tables(self) -> None:
        ReplayBase.metadata.create_all(self.engine)
        self._ensure_optional_columns()

    def _ensure_optional_columns(self) -> None:
        inspector = inspect(self.engine)
        if "phase_d_replay_decisions" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("phase_d_replay_decisions")}
        optional_columns = {
            "risk_approved": "BOOLEAN",
            "risk_reason": "TEXT",
            "order_id": "INTEGER",
            "fill_count": "INTEGER DEFAULT 0",
            "fill_qty_total": "INTEGER DEFAULT 0",
            "fill_avg_price": "FLOAT",
            "llm_input_tokens": "INTEGER",
            "llm_output_tokens": "INTEGER",
            "llm_total_tokens": "INTEGER",
            "llm_estimated_cost_usd": "FLOAT",
            "model_metadata": "JSON",
            "hold_cause": "VARCHAR(32)",
        }
        with self.engine.begin() as conn:
            for name, ddl_type in optional_columns.items():
                if name not in columns:
                    conn.execute(
                        text(
                            f"ALTER TABLE phase_d_replay_decisions "
                            f"ADD COLUMN {name} {ddl_type}"
                        )
                    )

    def create_run(
        self,
        name: str,
        config: Optional[dict] = None,
        input_events: Optional[Iterable[dict]] = None,
        notes: Optional[str] = None,
    ) -> dict:
        run_id = str(uuid.uuid4())
        record = ReplayRunRecord(
            id=run_id,
            name=name,
            status="running",
            started_at=datetime.now(timezone.utc),
            config=config or {},
            input_fingerprint=fingerprint_events(input_events or []),
            notes=notes,
        )
        with self.SessionLocal() as session:
            session.add(record)
            session.commit()
        return self.get_run(run_id)

    def complete_run(self, run_id: str, status: str = "completed") -> None:
        with self.SessionLocal() as session:
            record = session.get(ReplayRunRecord, run_id)
            if not record:
                return
            record.status = status
            record.completed_at = datetime.now(timezone.utc)
            session.commit()

    def record_decision(
        self,
        run_id: str,
        event_index: int,
        as_of_time: datetime,
        bot,
        decision,
        event_payload: Optional[dict] = None,
        fills: Optional[list] = None,
        risk_result=None,
        order_id: Optional[int] = None,
    ) -> None:
        fills = fills or []
        fill_qty_total = sum(int(getattr(fill, "quantity", 0) or 0) for fill in fills)
        fill_avg_price = (
            sum(float(fill.price) * int(fill.quantity) for fill in fills) / fill_qty_total
            if fill_qty_total > 0
            else None
        )
        snapshot = {}
        portfolio = getattr(bot, "portfolio", None)
        if portfolio is not None and hasattr(portfolio, "snapshot"):
            snapshot = portfolio.snapshot()

        record = ReplayDecisionRecord(
            run_id=run_id,
            event_index=event_index,
            as_of_time=as_of_time,
            bot_id=getattr(bot, "bot_id", "unknown"),
            bot_name=getattr(bot, "name", "unknown"),
            llm_provider=getattr(bot, "llm_provider", "unknown"),
            action=getattr(decision, "action", "HOLD"),
            hold_cause=getattr(decision, "hold_cause", None),
            ticker=getattr(decision, "ticker", None),
            quantity=getattr(decision, "quantity", None),
            limit_price=getattr(decision, "limit_price", None),
            reasoning=getattr(decision, "reasoning", "") or "",
            headline_used=getattr(decision, "headline_used", None),
            confidence=getattr(decision, "confidence", None),
            llm_input_tokens=getattr(decision, "llm_input_tokens", None),
            llm_output_tokens=getattr(decision, "llm_output_tokens", None),
            llm_total_tokens=getattr(decision, "llm_total_tokens", None),
            llm_estimated_cost_usd=getattr(decision, "llm_estimated_cost_usd", None),
            evidence_ids=list(getattr(decision, "evidence_ids", []) or []),
            evidence_urls=list(getattr(decision, "evidence_urls", []) or []),
            speculative=str(bool(getattr(decision, "speculative", False))).lower(),
            risk_approved=(
                bool(getattr(risk_result, "approved"))
                if risk_result is not None
                else None
            ),
            risk_reason=getattr(risk_result, "reason", None) if risk_result is not None else None,
            order_id=order_id,
            fill_count=len(fills),
            fill_qty_total=fill_qty_total,
            fill_avg_price=fill_avg_price,
            model_metadata=bot_model_metadata(
                bot,
                mode="replay",
                risk_limits=getattr(risk_result, "limits", None),
            ),
            portfolio_snapshot=snapshot,
            event_payload=event_payload or {},
        )
        with self.SessionLocal() as session:
            session.add(record)
            session.commit()

    def record_passive_fills(self, run_id: str, bot, fills: list) -> int:
        """Update replay decisions whose resting orders filled later in the run."""
        if not fills:
            return 0
        updated = 0
        snapshot = bot.portfolio.snapshot()
        with self.SessionLocal() as session:
            for fill in fills:
                row = (
                    session.query(ReplayDecisionRecord)
                    .filter(
                        ReplayDecisionRecord.run_id == run_id,
                        ReplayDecisionRecord.bot_id == bot.bot_id,
                        ReplayDecisionRecord.order_id == int(fill.order_id),
                    )
                    .order_by(ReplayDecisionRecord.id.desc())
                    .first()
                )
                if row is None:
                    continue
                quantity = int(fill.quantity)
                previous_qty = int(row.fill_qty_total or 0)
                previous_notional = float(row.fill_avg_price or 0.0) * previous_qty
                row.fill_count = int(row.fill_count or 0) + 1
                row.fill_qty_total = previous_qty + quantity
                row.fill_avg_price = (
                    previous_notional + float(fill.price) * quantity
                ) / row.fill_qty_total
                row.portfolio_snapshot = snapshot
                updated += 1
            session.commit()
        return updated

    def get_run(self, run_id: str) -> Optional[dict]:
        with self.SessionLocal() as session:
            record = session.get(ReplayRunRecord, run_id)
            return _run_to_dict(record) if record else None

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self.SessionLocal() as session:
            rows = (
                session.query(ReplayRunRecord)
                .order_by(ReplayRunRecord.started_at.desc())
                .limit(limit)
                .all()
            )
            return [_run_to_dict(row) for row in rows]

    def list_runs_by_input_fingerprint(
        self,
        input_fingerprint: str,
        limit: int = 20,
    ) -> list[dict]:
        if not input_fingerprint:
            return []
        with self.SessionLocal() as session:
            rows = (
                session.query(ReplayRunRecord)
                .filter(ReplayRunRecord.input_fingerprint == input_fingerprint)
                .order_by(ReplayRunRecord.started_at.desc())
                .limit(limit)
                .all()
            )
            return [_run_to_dict(row) for row in rows]

    def get_run_decisions(
        self,
        run_id: str,
        limit: int = 500,
        bot_id: Optional[str] = None,
    ) -> list[dict]:
        with self.SessionLocal() as session:
            query = session.query(ReplayDecisionRecord).filter(
                ReplayDecisionRecord.run_id == run_id
            )
            if bot_id:
                query = query.filter(ReplayDecisionRecord.bot_id == bot_id)
            rows = (
                query.order_by(
                    ReplayDecisionRecord.event_index.asc(),
                    ReplayDecisionRecord.id.asc(),
                )
                .limit(limit)
                .all()
            )
            return [_decision_to_dict(row) for row in rows]


class AsOfRagRepository:
    """
    Wrap a RagRepository so replay events cannot retrieve future documents.

    Normal live trading still uses the base repository directly. Replay code sets
    the wrapper's as-of time before each event.
    """

    def __init__(self, repository, as_of_date: Optional[datetime] = None):
        self.repository = repository
        self.as_of_date = as_of_date

    def set_as_of(self, as_of_date: Optional[datetime]) -> None:
        self.as_of_date = as_of_date

    def retrieve_evidence(self, *args, **kwargs):
        if kwargs.get("as_of_date") is None:
            kwargs["as_of_date"] = self.as_of_date
        return self.repository.retrieve_evidence(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.repository, name)


class HistoricalReplayRunner:
    """
    Deterministic harness for running bots over timestamped replay events.

    Events are plain dictionaries with at least a timestamp/as_of_time. Optional
    fields:
    - prices: {"AAPL": 188.0}
    - trending_headlines, recent_headlines, ticker_headlines
    """

    def __init__(
        self,
        bots,
        price_feed,
        news_feed,
        replay_store: Optional[ReplayStore] = None,
        engine_adapter=None,
        risk_limits: Optional[RiskLimits] = None,
        execute_orders: bool = True,
    ):
        self.bots = bots
        self.price_feed = price_feed
        self.news_feed = news_feed
        self.replay_store = replay_store
        self.engine_adapter = engine_adapter
        self.risk_limits = risk_limits or RiskLimits()
        self.execute_orders = execute_orders
        self._seeded_tickers: set[str] = set()
        self._result_by_order_id: dict[int, dict] = {}

    def run_events(self, events: Iterable[dict], run_id: Optional[str] = None) -> list[dict]:
        decisions = []
        event_list = list(events)
        for idx, event in enumerate(event_list):
            as_of_time = _parse_time(event.get("as_of_time") or event.get("timestamp"))
            self._apply_event(event)
            self._set_bot_as_of(as_of_time)
            for bot in self.bots:
                decision = bot.decide()
                order_id, fills, risk_result = self._execute_decision(bot, decision)
                fill_qty_total = sum(int(getattr(fill, "quantity", 0) or 0) for fill in fills)
                fill_avg_price = (
                    sum(float(fill.price) * int(fill.quantity) for fill in fills) / fill_qty_total
                    if fill_qty_total > 0
                    else None
                )
                result_row = {
                    "event_index": idx,
                    "as_of_time": as_of_time,
                    "bot_id": bot.bot_id,
                    "action": decision.action,
                    "ticker": decision.ticker,
                    "evidence_ids": list(decision.evidence_ids or []),
                    "speculative": decision.speculative,
                    "risk_approved": (
                        getattr(risk_result, "approved", None)
                        if risk_result is not None
                        else None
                    ),
                    "risk_reason": (
                        getattr(risk_result, "reason", None)
                        if risk_result is not None
                        else None
                    ),
                    "fill_count": len(fills),
                    "fill_qty_total": fill_qty_total,
                    "fill_avg_price": fill_avg_price,
                    "order_id": order_id,
                }
                decisions.append(result_row)
                if order_id is not None:
                    self._result_by_order_id[int(order_id)] = result_row
                if self.replay_store and run_id:
                    self.replay_store.record_decision(
                        run_id=run_id,
                        event_index=idx,
                        as_of_time=as_of_time,
                        bot=bot,
                        decision=decision,
                        event_payload=event,
                        fills=fills,
                        risk_result=risk_result,
                        order_id=order_id,
                    )
                self._settle_passive_fills(run_id)
        return decisions

    def _execute_decision(self, bot, decision) -> tuple[Optional[int], list, object]:
        action = str(getattr(decision, "action", "") or "").upper()
        if action == "HOLD":
            return None, [], None

        risk_result = risk_check_order(
            bot=bot,
            decision=decision,
            price_feed=self.price_feed,
            limits=self.risk_limits,
        )
        if not risk_result.approved:
            return None, [], risk_result
        if not self.execute_orders or self.engine_adapter is None:
            return None, [], risk_result

        order_type = "LIMIT" if getattr(decision, "limit_price", None) else "MARKET"
        price = getattr(decision, "limit_price", None)
        if price is None:
            price = self.price_feed.get_price(decision.ticker)
        order_id, fills = self.engine_adapter.submit(
            ticker=decision.ticker,
            side=decision.action,
            order_type=order_type,
            price=price,
            quantity=decision.quantity,
            bot_id=bot.bot_id,
        )
        for fill in fills:
            bot.portfolio.apply_fill(fill, strict=False)
        return order_id, fills, risk_result

    def _apply_event(self, event: dict) -> None:
        now = datetime.now(timezone.utc).timestamp()
        for ticker, price in (event.get("prices") or {}).items():
            cache = getattr(self.price_feed, "_cache", None)
            if isinstance(cache, dict):
                cache[str(ticker).upper()] = {
                    "price": float(price),
                    "ohlcv": event.get("ohlcv", {}).get(ticker, {}),
                    "timestamp": now,
                }

        if self.execute_orders and self.engine_adapter is not None:
            seed = getattr(self.engine_adapter, "seed_liquidity", None)
            if callable(seed):
                for ticker, price in (event.get("prices") or {}).items():
                    symbol = str(ticker).upper().strip()
                    if not symbol or symbol in self._seeded_tickers:
                        continue
                    seed(
                        ticker=symbol,
                        mid_price=float(price),
                        levels=SEED_LIQUIDITY_LEVELS,
                        quantity=SEED_LIQUIDITY_QTY,
                        spread_pct=SEED_LIQUIDITY_SPREAD_PCT,
                    )
                    self._seeded_tickers.add(symbol)

        if hasattr(self.news_feed, "_trending_cache"):
            self.news_feed._trending_cache = _normalize_headlines(
                event.get("trending_headlines", []),
                event,
            )
            self.news_feed._trending_ts = now
        if hasattr(self.news_feed, "_recent_cache"):
            self.news_feed._recent_cache = _normalize_headlines(
                event.get("recent_headlines", []),
                event,
            )
            self.news_feed._recent_ts = now
        if hasattr(self.news_feed, "_ticker_cache"):
            self.news_feed._ticker_cache = {
                str(ticker).upper(): _normalize_headlines(headlines, event)
                for ticker, headlines in (event.get("ticker_headlines", {}) or {}).items()
            }
            self.news_feed._ticker_ts = {
                str(ticker).upper(): now
                for ticker in self.news_feed._ticker_cache.keys()
            }

    def _set_bot_as_of(self, as_of_time: datetime) -> None:
        for bot in self.bots:
            repo = getattr(bot, "rag_repository", None)
            if isinstance(repo, AsOfRagRepository):
                repo.set_as_of(as_of_time)

    def _settle_passive_fills(self, run_id: Optional[str]) -> None:
        drainer = getattr(self.engine_adapter, "drain_fills", None)
        if not callable(drainer):
            return
        for bot in self.bots:
            fills = list(drainer(bot.bot_id) or [])
            if not fills:
                continue
            for fill in fills:
                bot.portfolio.apply_fill(fill, strict=False)
                result = self._result_by_order_id.get(int(fill.order_id))
                if result is not None:
                    previous_qty = int(result.get("fill_qty_total") or 0)
                    previous_avg = float(result.get("fill_avg_price") or 0.0)
                    new_qty = previous_qty + int(fill.quantity)
                    result["fill_count"] = int(result.get("fill_count") or 0) + 1
                    result["fill_qty_total"] = new_qty
                    result["fill_avg_price"] = (
                        previous_avg * previous_qty + float(fill.price) * int(fill.quantity)
                    ) / new_qty
            if self.replay_store is not None and run_id:
                self.replay_store.record_passive_fills(run_id, bot, fills)


def fingerprint_events(events: Iterable[dict]) -> str:
    payload = json.dumps(list(events), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)


def _run_to_dict(record: ReplayRunRecord) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "status": record.status,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "config": record.config or {},
        "input_fingerprint": record.input_fingerprint,
        "notes": record.notes,
        "decision_count": len(record.decisions or []),
    }


def _decision_to_dict(record: ReplayDecisionRecord) -> dict:
    return {
        "id": record.id,
        "run_id": record.run_id,
        "event_index": record.event_index,
        "as_of_time": record.as_of_time,
        "bot_id": record.bot_id,
        "bot_name": record.bot_name,
        "llm_provider": record.llm_provider,
        "action": record.action,
        "hold_cause": getattr(record, "hold_cause", None),
        "ticker": record.ticker,
        "quantity": record.quantity,
        "limit_price": record.limit_price,
        "reasoning": record.reasoning,
        "headline_used": record.headline_used,
        "confidence": record.confidence,
        "llm_input_tokens": record.llm_input_tokens,
        "llm_output_tokens": record.llm_output_tokens,
        "llm_total_tokens": record.llm_total_tokens,
        "llm_estimated_cost_usd": record.llm_estimated_cost_usd,
        "evidence_ids": record.evidence_ids or [],
        "evidence_urls": record.evidence_urls or [],
        "speculative": record.speculative == "true",
        "risk_approved": record.risk_approved,
        "risk_reason": record.risk_reason,
        "order_id": record.order_id,
        "fill_count": record.fill_count,
        "fill_qty_total": record.fill_qty_total,
        "fill_avg_price": record.fill_avg_price,
        "model_metadata": record.model_metadata or {},
        "portfolio_snapshot": record.portfolio_snapshot or {},
        "event_payload": record.event_payload or {},
    }


def _normalize_headlines(headlines, event: dict) -> list[dict]:
    normalized = []
    published_at = event.get("as_of_time") or event.get("timestamp")
    for item in headlines or []:
        if isinstance(item, str):
            row = {"title": item}
        else:
            row = dict(item)
        row.setdefault("title", "")
        row.setdefault("source", "Replay")
        row.setdefault("published_at", published_at or "")
        row.setdefault("age_minutes", 0)
        row.setdefault("age_label", "replay")
        row.setdefault("url", "")
        if row["title"]:
            normalized.append(row)
    return normalized
