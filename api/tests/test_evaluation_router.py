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
from api.routers.evaluation import get_replay_run, get_replay_run_decisions


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

    def get_run(self, run_id):
        return self.run if run_id == "run-1" else None

    def get_run_decisions(self, run_id, limit=500, bot_id=None):
        rows = self.decisions if run_id == "run-1" else []
        if bot_id:
            rows = [row for row in rows if row["bot_id"] == bot_id]
        return rows[:limit]


def _init_state():
    app_state.init(SimpleNamespace(replay_store=FakeReplayStore()))


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
