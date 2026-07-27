import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import OrderDecision
from portfolio import FillRecord, Portfolio
from replay import (
    AsOfRagRepository,
    HistoricalReplayRunner,
    ReplayStore,
    fingerprint_events,
)
from rag.repository import RagRepository
from risk import RiskLimits


def test_fingerprint_events_is_stable_for_identical_inputs():
    events = [{"timestamp": "2026-01-01T00:00:00Z", "prices": {"AAPL": 100}}]

    assert fingerprint_events(events) == fingerprint_events(list(events))


def test_replay_store_records_run_and_decision():
    store = ReplayStore("sqlite:///:memory:")
    events = [{"timestamp": "2026-01-01T00:00:00Z", "prices": {"AAPL": 100}}]
    run = store.create_run(
        name="smoke replay",
        config={"providers": ["claude", "openai"]},
        input_events=events,
    )
    bot = SimpleNamespace(
        bot_id="analyst-001-claude",
        name="AnalystBot (Claude)",
        llm_provider="claude",
        portfolio=Portfolio(100_000),
    )
    decision = OrderDecision(
        action="BUY",
        ticker="AAPL",
        quantity=10,
        limit_price=100.0,
        reasoning="evidence-backed replay decision",
        headline_used="AAPL margin expansion",
        confidence=0.7,
        evidence_ids=[1],
        evidence_urls=["https://example.com/aapl"],
        speculative=False,
    )

    store.record_decision(
        run_id=run["id"],
        event_index=0,
        as_of_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bot=bot,
        decision=decision,
        event_payload=events[0],
    )
    store.complete_run(run["id"])

    runs = store.list_runs()
    decisions = store.get_run_decisions(run["id"])

    assert runs[0]["status"] == "completed"
    assert runs[0]["decision_count"] == 1
    assert decisions[0]["bot_id"] == "analyst-001-claude"
    assert decisions[0]["action"] == "BUY"
    assert decisions[0]["evidence_ids"] == [1]


def test_replay_store_reconciles_later_fills_for_resting_orders():
    store = ReplayStore("sqlite:///:memory:")
    run = store.create_run(
        "passive fill replay",
        input_events=[{"timestamp": "2026-01-01T00:00:00Z", "prices": {"AAPL": 100}}],
    )
    bot = SimpleNamespace(
        bot_id="analyst-001-openai",
        name="AnalystBot (OpenAI)",
        llm_provider="openai",
        portfolio=Portfolio(100_000),
    )
    decision = OrderDecision(
        action="BUY",
        ticker="AAPL",
        quantity=10,
        limit_price=99.0,
        reasoning="resting evidence-backed order",
        headline_used="AAPL filing update",
        confidence=0.7,
        evidence_ids=[1],
        speculative=False,
    )
    store.record_decision(
        run_id=run["id"],
        event_index=0,
        as_of_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bot=bot,
        decision=decision,
        order_id=77,
    )

    fill = FillRecord(77, "AAPL", "BUY", 4, 98.5)
    bot.portfolio.apply_fill(fill)
    updated = store.record_passive_fills(run["id"], bot, [fill])
    stored = store.get_run_decisions(run["id"])[0]

    assert updated == 1
    assert stored["fill_count"] == 1
    assert stored["fill_qty_total"] == 4
    assert stored["fill_avg_price"] == 98.5
    assert stored["portfolio_snapshot"]["positions"]["AAPL"] == 4


def test_replay_store_lists_runs_by_input_fingerprint():
    store = ReplayStore("sqlite:///:memory:")
    events = [{"timestamp": "2026-01-01T00:00:00Z", "prices": {"AAPL": 100}}]
    first = store.create_run("first replay", input_events=events)
    second = store.create_run("second replay", input_events=events)
    other = store.create_run(
        "other replay",
        input_events=[{"timestamp": "2026-01-02T00:00:00Z", "prices": {"AAPL": 101}}],
    )

    rows = store.list_runs_by_input_fingerprint(first["input_fingerprint"])

    assert {row["id"] for row in rows} == {first["id"], second["id"]}
    assert other["id"] not in {row["id"] for row in rows}


def test_as_of_rag_repository_blocks_future_documents():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    old_doc = repo.add_document_with_chunks(
        ticker="AAPL",
        title="Old 10-Q",
        source_url="https://example.com/old",
        content="gross margin expansion revenue",
        chunks=[{"content": "gross margin expansion revenue", "start_pos": 0, "end_pos": 30}],
        published_at=datetime(2026, 1, 1),
    )
    future_doc = repo.add_document_with_chunks(
        ticker="AAPL",
        title="Future 10-Q",
        source_url="https://example.com/future",
        content="gross margin collapse revenue",
        chunks=[{"content": "gross margin collapse revenue", "start_pos": 0, "end_pos": 30}],
        published_at=datetime(2026, 2, 1),
    )
    undated_doc = repo.add_document_with_chunks(
        ticker="AAPL",
        title="Undated 10-Q",
        source_url="https://example.com/undated",
        content="gross margin collapse undated",
        chunks=[{"content": "gross margin collapse undated", "start_pos": 0, "end_pos": 29}],
        published_at=None,
    )

    wrapper = AsOfRagRepository(repo, as_of_date=datetime(2026, 1, 15))
    rows = wrapper.retrieve_evidence(
        ticker="AAPL",
        query_text="gross margin collapse",
        top_k=5,
    )

    assert {row["document_id"] for row in rows} == {old_doc.id}
    assert future_doc.id not in {row["document_id"] for row in rows}
    assert undated_doc.id not in {row["document_id"] for row in rows}


class ScriptedBot:
    def __init__(self, decision):
        self.bot_id = "scripted-001"
        self.name = "ScriptedBot"
        self.llm_provider = "scripted"
        self.portfolio = Portfolio(100_000)
        self._decision = decision

    def decide(self):
        return self._decision


class FakeEngine:
    def submit(self, ticker, side, order_type, price, quantity, bot_id):
        return 42, [FillRecord(42, ticker, side, quantity, price)]


class FakePriceFeed:
    def __init__(self):
        self._cache = {}

    def get_price(self, ticker):
        return self._cache[ticker]["price"]


class FakeNewsFeed:
    pass


def test_historical_replay_runner_executes_orders_and_records_fills():
    store = ReplayStore("sqlite:///:memory:")
    events = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "prices": {"AAPL": 100.0},
            "recent_headlines": ["AAPL revenue rises"],
        }
    ]
    run = store.create_run("order replay", input_events=events)
    decision = OrderDecision(
        action="BUY",
        ticker="AAPL",
        quantity=10,
        limit_price=None,
        reasoning="scripted buy",
        headline_used="AAPL revenue rises",
        confidence=0.8,
        evidence_ids=[],
        speculative=True,
    )
    bot = ScriptedBot(decision)
    runner = HistoricalReplayRunner(
        bots=[bot],
        price_feed=FakePriceFeed(),
        news_feed=FakeNewsFeed(),
        replay_store=store,
        engine_adapter=FakeEngine(),
    )

    results = runner.run_events(events, run_id=run["id"])
    stored = store.get_run_decisions(run["id"])

    assert results[0]["risk_approved"] is True
    assert results[0]["fill_count"] == 1
    assert stored[0]["order_id"] == 42
    assert stored[0]["fill_qty_total"] == 10
    assert stored[0]["fill_avg_price"] == 100.0
    assert stored[0]["risk_reason"] == "approved"
    assert bot.portfolio.snapshot()["positions"]["AAPL"] == 10


def test_historical_replay_runner_records_risk_rejections_without_order():
    store = ReplayStore("sqlite:///:memory:")
    events = [{"timestamp": "2026-01-01T00:00:00Z", "prices": {"AAPL": 100.0}}]
    run = store.create_run("risk replay", input_events=events)
    decision = OrderDecision(
        action="SELL",
        ticker="AAPL",
        quantity=10,
        limit_price=None,
        reasoning="scripted sell",
        headline_used=None,
        confidence=0.4,
        evidence_ids=[],
        speculative=True,
    )
    bot = ScriptedBot(decision)
    runner = HistoricalReplayRunner(
        bots=[bot],
        price_feed=FakePriceFeed(),
        news_feed=FakeNewsFeed(),
        replay_store=store,
        engine_adapter=FakeEngine(),
        risk_limits=RiskLimits(allow_short_selling=False),
    )

    results = runner.run_events(events, run_id=run["id"])
    stored = store.get_run_decisions(run["id"])

    assert results[0]["risk_approved"] is False
    assert "short selling disabled" in results[0]["risk_reason"]
    assert stored[0]["order_id"] is None
    assert stored[0]["fill_count"] == 0
