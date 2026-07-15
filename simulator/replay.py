"""Phase D historical replay storage and no-lookahead helpers."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy import JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


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
    ticker = Column(String(16), nullable=True)
    quantity = Column(Integer, nullable=True)
    limit_price = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=False)
    headline_used = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    evidence_ids = Column(JSON, nullable=False, default=list)
    evidence_urls = Column(JSON, nullable=False, default=list)
    speculative = Column(String(8), nullable=False, default="false")
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
            **({} if database_url.startswith("sqlite") else {"pool_size": 5, "max_overflow": 2}),
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.create_tables()

    def create_tables(self) -> None:
        ReplayBase.metadata.create_all(self.engine)

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
    ) -> None:
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
            ticker=getattr(decision, "ticker", None),
            quantity=getattr(decision, "quantity", None),
            limit_price=getattr(decision, "limit_price", None),
            reasoning=getattr(decision, "reasoning", "") or "",
            headline_used=getattr(decision, "headline_used", None),
            confidence=getattr(decision, "confidence", None),
            evidence_ids=list(getattr(decision, "evidence_ids", []) or []),
            evidence_urls=list(getattr(decision, "evidence_urls", []) or []),
            speculative=str(bool(getattr(decision, "speculative", False))).lower(),
            portfolio_snapshot=snapshot,
            event_payload=event_payload or {},
        )
        with self.SessionLocal() as session:
            session.add(record)
            session.commit()

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

    def get_run_decisions(self, run_id: str, limit: int = 500) -> list[dict]:
        with self.SessionLocal() as session:
            rows = (
                session.query(ReplayDecisionRecord)
                .filter(ReplayDecisionRecord.run_id == run_id)
                .order_by(ReplayDecisionRecord.event_index.asc(), ReplayDecisionRecord.id.asc())
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

    def __init__(self, bots, price_feed, news_feed, replay_store: Optional[ReplayStore] = None):
        self.bots = bots
        self.price_feed = price_feed
        self.news_feed = news_feed
        self.replay_store = replay_store

    def run_events(self, events: Iterable[dict], run_id: Optional[str] = None) -> list[dict]:
        decisions = []
        event_list = list(events)
        for idx, event in enumerate(event_list):
            as_of_time = _parse_time(event.get("as_of_time") or event.get("timestamp"))
            self._apply_event(event)
            self._set_bot_as_of(as_of_time)
            for bot in self.bots:
                decision = bot.decide()
                decisions.append({
                    "event_index": idx,
                    "as_of_time": as_of_time,
                    "bot_id": bot.bot_id,
                    "action": decision.action,
                    "ticker": decision.ticker,
                    "evidence_ids": list(decision.evidence_ids or []),
                    "speculative": decision.speculative,
                })
                if self.replay_store and run_id:
                    self.replay_store.record_decision(
                        run_id=run_id,
                        event_index=idx,
                        as_of_time=as_of_time,
                        bot=bot,
                        decision=decision,
                        event_payload=event,
                    )
        return decisions

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

        if hasattr(self.news_feed, "_trending_cache"):
            self.news_feed._trending_cache = event.get("trending_headlines", [])
            self.news_feed._trending_ts = now
        if hasattr(self.news_feed, "_recent_cache"):
            self.news_feed._recent_cache = event.get("recent_headlines", [])
            self.news_feed._recent_ts = now
        if hasattr(self.news_feed, "_ticker_cache"):
            self.news_feed._ticker_cache = event.get("ticker_headlines", {})
            self.news_feed._ticker_ts = {
                str(ticker).upper(): now
                for ticker in self.news_feed._ticker_cache.keys()
            }

    def _set_bot_as_of(self, as_of_time: datetime) -> None:
        for bot in self.bots:
            repo = getattr(bot, "rag_repository", None)
            if isinstance(repo, AsOfRagRepository):
                repo.set_as_of(as_of_time)


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
        "ticker": record.ticker,
        "quantity": record.quantity,
        "limit_price": record.limit_price,
        "reasoning": record.reasoning,
        "headline_used": record.headline_used,
        "confidence": record.confidence,
        "evidence_ids": record.evidence_ids or [],
        "evidence_urls": record.evidence_urls or [],
        "speculative": record.speculative == "true",
        "portfolio_snapshot": record.portfolio_snapshot or {},
        "event_payload": record.event_payload or {},
    }
