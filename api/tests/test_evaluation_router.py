import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from api import state as app_state
from api.routers import evaluation as evaluation_router
from api.routers.config import get_model_config, get_risk_limits
from api.routers.ops import get_evaluation_status, get_ingestion_status, get_rag_catalog, get_rag_document, get_rag_status, list_rag_documents
from api.routers.evaluation import (
    compare_replay_run_group,
    get_decision_brief,
    get_agent_activity,
    get_bot_behavior,
    get_bot_behavior_for_bot,
    get_evidence_chunks,
    get_live_evaluation_report,
    get_outcome_summary,
    get_replay_run,
    get_replay_run_decisions,
    get_recent_outcomes,
    get_replay_research,
    get_retrieval_history,
    get_retrieval_summary,
    get_risk_rejections,
    list_replay_fixtures,
)


class FakeReplayStore:
    def __init__(self):
        self.run = {
            "id": "run-1",
            "name": "Replay One",
            "status": "completed",
            "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "completed_at": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            "config": {"providers": ["claude"]},
            "input_fingerprint": "abc123",
            "notes": None,
            "decision_count": 2,
        }
        self.run_two = {
            "id": "run-2",
            "name": "Replay Two",
            "status": "completed",
            "started_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "completed_at": datetime(2026, 1, 2, 1, tzinfo=timezone.utc),
            "config": {"providers": ["openai"]},
            "input_fingerprint": "abc123",
            "notes": None,
            "decision_count": 1,
        }
        self.decisions = [
            {
                "id": 1,
                "run_id": "run-1",
                "event_index": 0,
                "as_of_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "llm_provider": "claude",
                "action": "BUY",
                "ticker": "AAPL",
                "quantity": 10,
                "limit_price": None,
                "reasoning": "cited evidence",
                "headline_used": "AAPL beats",
                "confidence": 0.8,
                "evidence_ids": [7],
                "evidence_urls": ["https://example.com/aapl"],
                "speculative": False,
                "risk_approved": True,
                "risk_reason": "approved",
                "order_id": 42,
                "fill_count": 1,
                "fill_qty_total": 10,
                "fill_avg_price": 100.0,
                "portfolio_snapshot": {},
                "event_payload": {},
            },
            {
                "id": 2,
                "run_id": "run-1",
                "event_index": 0,
                "as_of_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "bot_id": "bear-001-claude",
                "bot_name": "BearBot (Claude)",
                "llm_provider": "claude",
                "action": "SELL",
                "ticker": "AAPL",
                "quantity": 10,
                "limit_price": None,
                "reasoning": "risk rejected",
                "headline_used": None,
                "confidence": 0.4,
                "evidence_ids": [],
                "evidence_urls": [],
                "speculative": True,
                "risk_approved": False,
                "risk_reason": "short selling disabled",
                "order_id": None,
                "fill_count": 0,
                "fill_qty_total": 0,
                "fill_avg_price": None,
                "portfolio_snapshot": {},
                "event_payload": {},
            },
        ]
        self.decisions_two = [
            {
                "id": 3,
                "run_id": "run-2",
                "event_index": 0,
                "as_of_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "bot_id": "analyst-001-openai",
                "bot_name": "AnalystBot (OpenAI)",
                "llm_provider": "openai",
                "action": "HOLD",
                "ticker": None,
                "quantity": None,
                "limit_price": None,
                "reasoning": "wait",
                "headline_used": None,
                "confidence": 0.2,
                "evidence_ids": [],
                "evidence_urls": [],
                "speculative": False,
                "risk_approved": None,
                "risk_reason": None,
                "order_id": None,
                "fill_count": 0,
                "fill_qty_total": 0,
                "fill_avg_price": None,
                "portfolio_snapshot": {},
                "event_payload": {},
            },
        ]

    def get_run(self, run_id):
        if run_id == "run-1":
            return self.run
        if run_id == "run-2":
            return self.run_two
        return None

    def list_runs_by_input_fingerprint(self, input_fingerprint, limit=20):
        rows = [self.run, self.run_two]
        return [row for row in rows if row["input_fingerprint"] == input_fingerprint][:limit]

    def get_run_decisions(self, run_id, limit=500, bot_id=None):
        if run_id == "run-1":
            rows = self.decisions
        elif run_id == "run-2":
            rows = self.decisions_two
        else:
            rows = []
        if bot_id:
            rows = [row for row in rows if row["bot_id"] == bot_id]
        return rows[:limit]


class FakeReasoningLog:
    def __init__(self):
        self.rows = [
            {
                "id": 1,
                "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "llm_provider": "claude",
                "action": "BUY",
                "ticker": "AAPL",
                "quantity": 10,
                "limit_price": None,
                "reasoning": "cited filing",
                "headline_used": "AAPL beats",
                "confidence": 0.8,
                "evidence_ids": [7],
                "evidence_urls": ["https://example.com/aapl"],
                "speculative": False,
                "fill_count": 1,
                "fill_qty_total": 10,
                "fill_avg_price": 100.0,
                "portfolio_snapshot": {"cash": 99000, "positions": {"AAPL": 10}, "cost_basis": {"AAPL": 100}, "total_value": 100000},
            },
            {
                "id": 2,
                "timestamp": datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
                "bot_id": "bear-001-openai",
                "bot_name": "BearBot (OpenAI)",
                "llm_provider": "openai",
                "action": "HOLD",
                "ticker": None,
                "quantity": None,
                "limit_price": None,
                "reasoning": "Risk check rejected original order (SELL 10 AAPL): short selling disabled",
                "headline_used": None,
                "confidence": 0.3,
                "evidence_ids": [],
                "evidence_urls": [],
                "speculative": True,
                "fill_count": 0,
                "fill_qty_total": 0,
                "fill_avg_price": None,
                "portfolio_snapshot": {"cash": 100000, "positions": {}, "cost_basis": {}, "total_value": 100000},
            },
        ]

    def get_decisions(self, bot_id=None, action=None, limit=100, since=None, before=None):
        rows = self.rows
        if bot_id:
            rows = [row for row in rows if row["bot_id"] == bot_id]
        if action:
            rows = [row for row in rows if row["action"] == action]
        return rows[:limit]

    def get_agent_activity(self, bot_id=None, limit=100, event_type=None, stage=None):
        rows = [
            {
                "id": 10,
                "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "decision_id": 1,
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "llm_provider": "claude",
                "event_type": "tool",
                "stage": "rag_retrieval",
                "tool_name": "retrieve_evidence",
                "status": "succeeded",
                "summary": "Retrieved 1 evidence chunk",
                "duration_ms": 12.3,
                "evidence_ids": [7],
                "metadata": {"top_k": 1},
            }
        ]
        if bot_id:
            rows = [row for row in rows if row["bot_id"] == bot_id]
        if event_type:
            rows = [row for row in rows if row["event_type"] == event_type]
        if stage:
            rows = [row for row in rows if row["stage"] == stage]
        return rows[:limit]

    def get_decision_outcomes(self, bot_id=None, horizon=None, status=None, limit=1000, since=None, before=None):
        rows = [
            {
                "id": 100,
                "decision_id": 1,
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "llm_provider": "claude",
                "decision_timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "horizon": "1h",
                "horizon_seconds": 3600,
                "observed_at": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                "action": "BUY",
                "ticker": "AAPL",
                "quantity": 10,
                "entry_price": 100.0,
                "mark_price": 110.0,
                "portfolio_value_at_decision": 100000.0,
                "portfolio_value_at_observation": 100100.0,
                "position_pnl": 100.0,
                "portfolio_delta": 100.0,
                "llm_estimated_cost_usd": 0.02,
                "net_after_llm_cost": 99.98,
                "filled_quantity": 10,
                "risk_approved": True,
                "outcome_status": "profitable",
                "metadata": {},
            },
            {
                "id": 101,
                "decision_id": 2,
                "bot_id": "bear-001-openai",
                "bot_name": "BearBot (OpenAI)",
                "llm_provider": "openai",
                "decision_timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "horizon": "1h",
                "horizon_seconds": 3600,
                "observed_at": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                "action": "SELL",
                "ticker": "AAPL",
                "quantity": 10,
                "entry_price": None,
                "mark_price": 110.0,
                "portfolio_value_at_decision": 100000.0,
                "portfolio_value_at_observation": 100000.0,
                "position_pnl": 0.0,
                "portfolio_delta": 0.0,
                "llm_estimated_cost_usd": 0.01,
                "net_after_llm_cost": -0.01,
                "filled_quantity": 0,
                "risk_approved": False,
                "outcome_status": "risk_rejected",
                "metadata": {},
            },
        ]
        if bot_id:
            rows = [row for row in rows if row["bot_id"] == bot_id]
        if horizon:
            rows = [row for row in rows if row["horizon"] == horizon]
        if status:
            rows = [row for row in rows if row["outcome_status"] == status]
        return rows[:limit]


class FakePriceFeed:
    def get_price(self, ticker):
        prices = {
            "NVDA": 180.0,
            "AMD": 165.0,
            "AVGO": 310.0,
            "MSFT": 420.0,
            "GOOGL": 190.0,
            "AMZN": 220.0,
            "TSLA": 260.0,
            "SPY": 680.0,
            "QQQ": 600.0,
        }
        return prices[str(ticker).upper()]

    def get_tradable_tickers(self):
        return ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA"]


class FakeRagRepository:
    engine_url = "postgresql://marketsim:secret-password@internal-db/marketsim"

    documents = [
        {
            "id": 70,
            "ticker": "AAPL",
            "title": "Apple 10-Q",
            "source_url": "https://example.com/aapl",
            "source_type": "sec_filing",
            "source_name": "SEC EDGAR",
            "form_type": "10-Q",
            "cik": "0000320193",
            "accession_no": "0000320193-26-000001",
            "published_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "content_length": 1234,
            "chunk_count": 2,
            "pending_embedding_count": 0,
            "content_preview": "gross margin expanded and revenue increased",
        }
    ]

    def get_chunks_by_ids(self, chunk_ids):
        rows = {
            7: {
                "chunk_id": 7,
                "document_id": 70,
                "ticker": "AAPL",
                "title": "Apple 10-Q",
                "source_url": "https://example.com/aapl",
                "source_type": "sec",
                "source_name": "SEC EDGAR",
                "form_type": "10-Q",
                "cik": "0000320193",
                "accession_no": "0000320193-26-000001",
                "published_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "content": "gross margin expanded",
                "start_pos": 0,
                "end_pos": 21,
            }
        }
        return [rows[chunk_id] for chunk_id in chunk_ids if chunk_id in rows]

    def summarize_documents(self):
        return {
            "document_count": 1,
            "chunk_count": 2,
            "pending_embedding_count": 0,
            "latest_created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "latest_published_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "tickers": [{"value": "AAPL", "count": 1}],
            "source_types": [{"value": "sec_filing", "count": 1}],
            "form_types": [{"value": "10-Q", "count": 1}],
        }

    def deduplicate_documents(self, dry_run=True):
        assert dry_run is True
        return {
            "duplicate_group_count": 0,
            "duplicate_document_count": 0,
            "duplicate_chunk_count": 0,
        }

    def list_documents(self, ticker=None, source_type=None, form_type=None, query_text=None, limit=50, offset=0):
        rows = list(self.documents)
        if ticker:
            rows = [row for row in rows if row["ticker"] == ticker]
        if source_type:
            rows = [row for row in rows if row["source_type"] == source_type]
        if form_type:
            rows = [row for row in rows if row["form_type"] == form_type]
        if query_text:
            needle = query_text.lower()
            rows = [row for row in rows if needle in row["title"].lower()]
        return {"documents": rows[offset:offset + limit], "total": len(rows), "limit": limit, "offset": offset}

    def get_document_detail(self, document_id, chunk_limit=12):
        if document_id != 70:
            return None
        row = dict(self.documents[0])
        row["chunks"] = [
            {
                "chunk_id": 7,
                "start_pos": 0,
                "end_pos": 21,
                "has_embedding": True,
                "content": "gross margin expanded",
            }
        ][:chunk_limit]
        return row

    def get_document_chunk_id_map(self, document_ids):
        return {70: [7, 8]} if 70 in document_ids else {}

    def retrieve_evidence(self, ticker, query_text, top_k, embedding_service=None, as_of_date=None):
        return [
            {
                "chunk_id": 7,
                "document_id": 70,
                "ticker": ticker,
                "source_url": "https://example.com/aapl",
                "accession_no": "0000320193-26-000001",
                "content": "gross margin expanded and revenue increased",
            }
        ][:top_k]

    def count_documents(self):
        return 1

    def count_chunks(self):
        return 1

    def get_chunks_without_embeddings(self, limit=100):
        return []

    def list_job_status(self, job_type=None, limit=20):
        return [
            {
                "id": 1,
                "job_type": job_type or "embedding",
                "status": "succeeded",
                "attempts": 1,
                "max_attempts": 1,
                "metadata": {"embedded": 0, "tickers": ["AAPL"], "forms": ["10-Q"], "updated_tickers": ["AAPL"]},
            }
        ][:limit]

    def summarize_job_status(self):
        return {
            "total": 1,
            "by_type": {"embedding": {"succeeded": 1}},
            "by_status": {"succeeded": 1},
            "latest_started_at": None,
            "latest_finished_at": None,
        }


def _init_state():
    app_state.init(SimpleNamespace(
        bots=[],
        replay_store=FakeReplayStore(),
        reasoning_log=FakeReasoningLog(),
        rag_repository=FakeRagRepository(),
        embedding_service=None,
        risk_limits=None,
        scheduler=None,
        evaluation_scheduler=SimpleNamespace(status=lambda: {
            "enabled": True,
            "running": True,
            "outcome_labeling": {
                "enabled": True,
                "interval_seconds": 3600.0,
                "horizons": ["1h", "6h"],
                "decision_limit": 2000,
                "next_run_at": "2026-01-01T01:00:00+00:00",
                "last_run": {"status": "succeeded", "created_count": 3},
            },
            "replay_matrix": {
                "enabled": False,
                "interval_seconds": 86400.0,
                "fixtures": ["sample_earnings_beat.json"],
                "provider_sets": ["claude", "openai"],
                "bots": ["analyst", "bear", "macro"],
                "execute_orders": False,
                "max_fixtures_per_run": 1,
                "next_run_at": None,
                "last_run": None,
            },
            "recent_failures": [],
        }),
        price_feed=FakePriceFeed(),
    ))


def test_get_decision_brief_returns_focused_payload():
    _init_state()

    result = asyncio.run(get_decision_brief(ticker="NVDA", sector="ai_infrastructure"))

    assert result["ticker"] == "NVDA"
    assert result["sector"] == "ai_infrastructure"
    assert result["universe"]["tradable_tickers"] == ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA"]
    assert result["universe"]["benchmark_tickers"] == ["SPY", "QQQ"]
    assert result["recommendation"]["category"] in {"add", "wait", "reduce", "research_more"}
    assert result["so_what"]
    assert result["what_changed"]["ticker"]["ticker"] == "NVDA"
    assert [row["ticker"] for row in result["what_changed"]["normalized_series"]] == ["NVDA", "SPY", "QQQ"]
    assert {row["benchmark"] for row in result["benchmark_check"]["comparisons"]} >= {"SPY", "QQQ"}
    assert result["evidence"][0]["ticker"] == "NVDA"
    assert any(row["perspective"] == "Analyst" for row in result["agent_debate"])
    assert result["caveats"]


def test_get_live_evaluation_report_is_monitoring_readout():
    _init_state()

    result = asyncio.run(
        get_live_evaluation_report(
            period_days=7,
            min_samples=1,
            horizon="1h",
            limit=100,
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            until=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert result["report_type"] == "live_evaluation"
    assert result["mode"] == "decision_grade"
    assert result["sample"]["labeled_decision_count"] == 2
    assert result["outcomes"]["selected_horizon"] == "1h"
    assert result["by_provider"]["claude"]["outcomes"]["profitable_count"] == 1
    assert result["benchmark_comparison"]["available"] is False
    assert "# Live Evaluation Report" in result["markdown"]


def test_get_decision_brief_rejects_outside_universe_ticker():
    _init_state()

    try:
        asyncio.run(get_decision_brief(ticker="AAPL", sector="ai_infrastructure"))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "outside the focused universe" in str(getattr(exc, "detail", ""))
    else:
        raise AssertionError("outside-universe ticker should be rejected")


def test_get_decision_brief_can_skip_slow_evidence_for_arena():
    _init_state()

    result = asyncio.run(
        get_decision_brief(
            ticker="NVDA",
            sector="ai_infrastructure",
            include_evidence=False,
        )
    )

    assert result["evidence_included"] is False
    assert result["evidence"] == []
    assert result["what_changed"]["normalized_series"]


def test_get_replay_run_returns_summary_and_decisions():
    _init_state()

    result = asyncio.run(get_replay_run("run-1", decision_limit=500))

    assert result["run"]["id"] == "run-1"
    assert result["summary"]["totals"]["trade_count"] == 2
    assert result["summary"]["totals"]["citation_rate"] == 0.5
    assert len(result["decisions"]) == 2


def test_get_replay_run_decisions_filters_by_bot():
    _init_state()

    result = asyncio.run(
        get_replay_run_decisions("run-1", limit=500, bot_id="bear-001-claude")
    )

    assert len(result) == 1
    assert result[0]["bot_name"] == "BearBot (Claude)"


def test_compare_replay_run_group_returns_shared_fingerprint_report():
    _init_state()

    result = asyncio.run(
        compare_replay_run_group(run_id="run-1", run_limit=20, decision_limit=500)
    )

    assert result["input_fingerprint"] == "abc123"
    assert result["run_count"] == 2
    assert {row["run"]["id"] for row in result["runs"]} == {"run-1", "run-2"}
    run_one = next(row for row in result["runs"] if row["run"]["id"] == "run-1")
    assert run_one["metrics"]["risk_rejection_count"] == 1


def test_get_bot_behavior_returns_per_bot_summaries():
    _init_state()

    result = asyncio.run(get_bot_behavior(limit=500))

    assert result["bot_count"] == 2
    assert result["decision_window"]["returned"] == 2
    bear = next(row for row in result["bots"] if row["bot_id"] == "bear-001-openai")
    assert bear["risk_rejection_count"] == 1


def test_get_bot_behavior_for_bot_returns_timeline():
    _init_state()

    result = asyncio.run(get_bot_behavior_for_bot("analyst-001-claude", limit=500))

    assert result["bot"]["bot_name"] == "AnalystBot (Claude)"
    assert len(result["timeline"]) == 1
    assert result["timeline"][0]["evidence_count"] == 1


def test_get_risk_rejections_returns_recent_rejected_decisions():
    _init_state()

    result = asyncio.run(get_risk_rejections(limit=10, decision_window=500))

    assert result["risk_rejection_count"] == 1
    assert result["decisions"][0]["bot_id"] == "bear-001-openai"


def test_get_outcome_summary_returns_live_outcome_metrics():
    _init_state()

    result = asyncio.run(get_outcome_summary(horizon="1h", limit=500))

    assert result["totals"]["outcome_count"] == 2
    assert result["totals"]["profitable_count"] == 1
    assert result["totals"]["risk_rejected_count"] == 1
    assert result["totals"]["total_net_after_llm_cost"] == 99.97
    assert result["by_provider"]["claude"]["win_rate"] == 1.0
    assert result["outcome_window"]["horizon"] == "1h"


def test_get_recent_outcomes_filters_by_status():
    _init_state()

    result = asyncio.run(
        get_recent_outcomes(
            horizon="1h",
            status="risk_rejected",
            bot_id=None,
            limit=20,
        )
    )

    assert result["returned"] == 1
    assert result["outcomes"][0]["bot_id"] == "bear-001-openai"
    assert result["filters"]["status"] == "risk_rejected"


def test_get_agent_activity_returns_public_safe_timeline():
    _init_state()

    result = asyncio.run(
        get_agent_activity(
            bot_id="analyst-001-claude",
            event_type=None,
            stage=None,
            limit=20,
        )
    )

    assert result["returned"] == 1
    assert result["activity"][0]["tool_name"] == "retrieve_evidence"
    assert result["activity"][0]["evidence_ids"] == [7]


def test_get_evidence_chunks_returns_chunks_and_missing_ids():
    _init_state()

    result = asyncio.run(get_evidence_chunks(chunk_ids="7,999", limit=100))

    assert result["requested_ids"] == [7, 999]
    assert result["chunks"][0]["chunk_id"] == 7
    assert result["chunks"][0]["form_type"] == "10-Q"
    assert result["missing_ids"] == [999]


def test_get_retrieval_summary_runs_case_file(tmp_path, monkeypatch):
    _init_state()
    case_file = tmp_path / "cases.json"
    case_file.write_text(
        """
        {
          "name": "test cases",
          "cases": [
            {
              "name": "margin",
              "ticker": "AAPL",
              "query_text": "gross margin",
              "expected_text_contains": ["margin"],
              "top_k": 3
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation_router, "RETRIEVAL_CASES_DIR", tmp_path)

    result = asyncio.run(
        get_retrieval_summary(case_file="cases.json", top_k=None, use_embeddings=False)
    )

    assert result["metadata"]["name"] == "test cases"
    assert result["hit_count"] == 1
    assert result["cases"][0]["hit_rank"] == 1


def test_get_retrieval_history_reads_jsonl(tmp_path, monkeypatch):
    history = tmp_path / "history.jsonl"
    history.write_text(
        '{"ran_at":"2026-01-01T00:00:00Z","recall_at_k":1.0}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation_router, "RETRIEVAL_HISTORY_PATH", history)

    result = asyncio.run(get_retrieval_history(limit=5))

    assert result["history"][0]["recall_at_k"] == 1.0


def test_list_replay_fixtures_summarizes_available_scenarios(tmp_path, monkeypatch):
    fixture = tmp_path / "sample_fixture.json"
    fixture.write_text(
        """
        {
          "name": "Sample Fixture",
          "description": "A deterministic replay fixture.",
          "config": {
            "scenario": "unit_test",
            "tickers": ["AAPL"],
            "expected_notes": ["Analyst should cite evidence."]
          },
          "events": [
            {
              "timestamp": "2026-01-01T14:30:00Z",
              "prices": {"AAPL": 100.0},
              "ticker_headlines": {"MSFT": [{"title": "MSFT headline"}]},
              "expected_notes": ["No future evidence should leak."]
            },
            {
              "timestamp": "2026-01-01T15:30:00Z",
              "prices": {"AAPL": 101.0, "SPY": 500.0}
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    support_file = tmp_path / "historical_macro_context.json"
    support_file.write_text(
        '{"headlines":[{"title":"CPI release","published_at":"2026-01-01T13:30:00Z"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation_router, "REPLAY_EVENTS_DIR", tmp_path)

    result = asyncio.run(list_replay_fixtures())

    assert result["default_execute_orders"] is False
    assert result["recommended_bots"] == ["analyst", "bear", "macro"]
    assert result["errors"] == []
    assert len(result["fixtures"]) == 1
    row = result["fixtures"][0]
    assert row["file_name"] == "sample_fixture.json"
    assert row["name"] == "Sample Fixture"
    assert row["scenario"] == "unit_test"
    assert row["event_count"] == 2
    assert row["tickers"] == ["AAPL", "MSFT", "SPY"]
    assert row["start_time"] == "2026-01-01T14:30:00Z"
    assert row["end_time"] == "2026-01-01T15:30:00Z"
    assert row["api_request"]["event_file"] == "sample_fixture.json"
    assert "--no-orders" in row["matrix_command"]
    assert "No future evidence should leak." in row["expected_notes"]


def test_get_replay_research_loads_artifacts(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    dataset_dir = tmp_path / "datasets"
    report_dir.mkdir()
    dataset_dir.mkdir()
    standings = {
        "generated_at": "2026-08-18T00:00:00Z",
        "benchmark": "SPY",
        "overall": {
            "decision_count": 2,
            "trade_count": 1,
            "directional_accuracy_1d": 1.0,
            "beat_benchmark_rate_1d": 0.0,
        },
        "standings": {
            "bot_provider": [
                {
                    "label": "AnalystBot (Claude)",
                    "decision_count": 2,
                    "trade_count": 1,
                    "intent_mark_pnl_1d": 10.0,
                }
            ]
        },
        "lessons": {"positive": ["A tiny fixture worked."], "negative": []},
        "model_suite_summary": {
            "directional_correct_1d": {
                "status": "ok",
                "usable_rows": 1,
                "best_model_by_test_accuracy": "dummy_majority",
            }
        },
    }
    model_suite = {
        "generated_at": "2026-08-18T00:00:00Z",
        "dataset": "data/ml/datasets/replay_decisions_unit.csv",
        "row_count": 2,
        "feature_columns": ["confidence"],
        "model_names": ["dummy_majority"],
        "targets": {
            "directional_correct_1d": {
                "status": "ok",
                "usable_rows": 1,
                "label_counts": {"1": 1},
                "warnings": [],
                "best_model_by_test_accuracy": "dummy_majority",
                "best_model_by_test_f1": "dummy_majority",
                "models": {
                    "dummy_majority": {
                        "metrics": {
                            "test": {
                                "row_count": 1,
                                "accuracy": 1.0,
                                "f1": 1.0,
                            }
                        }
                    }
                },
            }
        },
    }
    manifest = {"generated_at": "2026-08-18T00:00:01Z", "version": "unit"}
    summary = {
        "row_count": 2,
        "cost_summary": {
            "available": True,
            "recorded_cost_count": 2,
            "total_estimated_llm_cost_usd": 0.05,
        },
    }
    (report_dir / "replay_standings_unit.json").write_text(json.dumps(standings), encoding="utf-8")
    (report_dir / "model_suite_unit.json").write_text(json.dumps(model_suite), encoding="utf-8")
    (report_dir / "refresh_manifest_unit.json").write_text(json.dumps(manifest), encoding="utf-8")
    (report_dir / "replay_research_report_unit.md").write_text("# Unit report\n", encoding="utf-8")
    (dataset_dir / "replay_decisions_unit.summary.json").write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(evaluation_router, "REPLAY_RESEARCH_REPORT_DIR", report_dir)
    monkeypatch.setattr(evaluation_router, "REPLAY_RESEARCH_DATASET_DIR", dataset_dir)

    result = asyncio.run(get_replay_research(version="unit"))

    assert result["available"] is True
    assert result["overall"]["decision_count"] == 2
    assert result["cost_summary"]["total_estimated_llm_cost_usd"] == 0.05
    assert result["model_suite"]["targets"]["directional_correct_1d"]["models"]["dummy_majority"]["test_accuracy"] == 1.0
    assert result["markdown_report"] == "# Unit report\n"


def test_get_replay_research_returns_unavailable_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation_router, "REPLAY_RESEARCH_REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(evaluation_router, "REPLAY_RESEARCH_DATASET_DIR", tmp_path / "datasets")

    result = asyncio.run(get_replay_research(version="missing"))

    assert result["available"] is False
    assert "refresh_replay_research.py" in result["expected_command"]


def test_config_and_ops_endpoints_return_read_only_status():
    _init_state()

    model_result = asyncio.run(get_model_config())
    risk_result = asyncio.run(get_risk_limits())
    rag_result = asyncio.run(get_rag_status())
    ingestion_result = asyncio.run(get_ingestion_status())
    evaluation_status = asyncio.run(get_evaluation_status())

    assert model_result["providers"]["openai"]["model"]
    assert model_result["public_read_only"] is True
    if model_result["live_bots"]:
        assert "prompt_hash" not in model_result["live_bots"][0]
    assert risk_result["risk_limits"]["max_order_quantity"] == 250
    assert rag_result["document_count"] == 1
    assert "engine_url" not in rag_result
    assert ingestion_result["public_read_only"] is True
    assert ingestion_result["rag"]["job_summary"]["total"] == 1
    assert "job_backend" not in ingestion_result
    assert evaluation_status["configured"] is True
    assert evaluation_status["running"] is True
    assert evaluation_status["outcome_labeling"]["enabled"] is True
    assert "recent_failures" not in evaluation_status


def test_rag_catalog_and_document_library_endpoints_return_metadata():
    _init_state()

    catalog = asyncio.run(get_rag_catalog())
    documents = asyncio.run(
        list_rag_documents(
            ticker="AAPL",
            source_type=None,
            form_type=None,
            q=None,
            limit=50,
            offset=0,
        )
    )
    detail = asyncio.run(get_rag_document(70, chunk_limit=5))

    assert catalog["document_count"] == 1
    assert catalog["tickers"][0]["value"] == "AAPL"
    assert catalog["duplicate_document_count"] == 0
    assert documents["total"] == 1
    assert documents["documents"][0]["category"] == "Quarterly SEC filing"
    assert documents["documents"][0]["citation_count"] == 1
    assert "SEC filing poll" in documents["documents"][0]["ingestion_reason"]
    assert detail["chunks"][0]["content"] == "gross margin expanded"
