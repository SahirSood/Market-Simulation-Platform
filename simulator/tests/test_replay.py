import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import OrderDecision
from portfolio import Portfolio
from replay import AsOfRagRepository, ReplayStore, fingerprint_events
from rag.repository import RagRepository


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

    wrapper = AsOfRagRepository(repo, as_of_date=datetime(2026, 1, 15))
    rows = wrapper.retrieve_evidence(
        ticker="AAPL",
        query_text="gross margin collapse",
        top_k=5,
    )

    assert {row["document_id"] for row in rows} == {old_doc.id}
    assert future_doc.id not in {row["document_id"] for row in rows}
