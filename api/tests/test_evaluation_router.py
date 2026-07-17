import asyncio
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
from api.routers.ops import get_ingestion_status, get_rag_status
from api.routers.evaluation import (
    compare_replay_run_group,
    get_bot_behavior,
    get_bot_behavior_for_bot,
    get_evidence_chunks,
    get_replay_run,
    get_replay_run_decisions,
    get_retrieval_summary,
    get_risk_rejections,
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


class FakeRagRepository:
    engine_url = "sqlite:///:memory:"

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


def _init_state():
    app_state.init(SimpleNamespace(
        bots=[],
        replay_store=FakeReplayStore(),
        reasoning_log=FakeReasoningLog(),
        rag_repository=FakeRagRepository(),
        embedding_service=None,
        risk_limits=None,
        scheduler=None,
    ))


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


def test_config_and_ops_endpoints_return_read_only_status():
    _init_state()

    model_result = asyncio.run(get_model_config())
    risk_result = asyncio.run(get_risk_limits())
    rag_result = asyncio.run(get_rag_status())
    ingestion_result = asyncio.run(get_ingestion_status())

    assert model_result["providers"]["openai"]["model"]
    assert risk_result["risk_limits"]["max_order_quantity"] == 250
    assert rag_result["document_count"] == 1
    assert ingestion_result["job_backend"] == "local_scripts"
