import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import evaluation_scheduler as scheduler_module
from evaluation_scheduler import EvaluationScheduler


class FakePriceFeed:
    def __init__(self, prices):
        self.prices = prices

    def get_price(self, ticker):
        return self.prices[ticker]


class FakeReasoningLog:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.decisions = [
            {
                "id": 1,
                "timestamp": now - timedelta(hours=2),
                "bot_id": "analyst-001",
                "bot_name": "AnalystBot",
                "llm_provider": "claude",
                "action": "BUY",
                "ticker": "AAPL",
                "quantity": 10,
                "fill_qty_total": 10,
                "fill_avg_price": 100.0,
                "llm_estimated_cost_usd": 0.02,
                "portfolio_snapshot": {
                    "cash": 99_000,
                    "positions": {"AAPL": 10},
                    "cost_basis": {"AAPL": 100},
                    "total_value": 100_000,
                },
            }
        ]
        self.outcomes = []
        self.recorded = []

    def get_decisions(self, limit=1000, **kwargs):
        return self.decisions[:limit]

    def get_decision_outcomes(self, limit=1000, **kwargs):
        return self.outcomes[:limit]

    def record_decision_outcome(self, **payload):
        self.recorded.append(payload)
        self.outcomes.append({**payload, "id": len(self.outcomes) + 1})
        return len(self.outcomes)


def test_run_outcome_update_once_records_due_labels():
    reasoning_log = FakeReasoningLog()
    scheduler = EvaluationScheduler(
        reasoning_log=reasoning_log,
        price_feed=FakePriceFeed({"AAPL": 110.0}),
        replay_store=SimpleNamespace(),
        enabled=False,
        outcome_horizons=("1h",),
    )

    result = scheduler.run_outcome_update_once()

    assert result["status"] == "succeeded"
    assert result["created_count"] == 1
    assert reasoning_log.recorded[0]["horizon"] == "1h"
    assert reasoning_log.recorded[0]["outcome_status"] == "profitable"


def test_run_replay_matrix_once_uses_configured_safe_defaults(monkeypatch):
    calls = []

    def fake_load_replay_event_file(path, root):
        return "Replay Fixture", {"scenario": "unit"}, [
            {"timestamp": "2026-01-01T14:30:00Z", "prices": {"AAPL": 100.0}}
        ]

    def fake_run_historical_replay(**kwargs):
        calls.append(kwargs)
        return {
            "run_id": f"run-{len(calls)}",
            "status": "completed",
            "decision_count": 3,
            "input_fingerprint": "abc123",
        }

    monkeypatch.setattr(scheduler_module, "load_replay_event_file", fake_load_replay_event_file)
    monkeypatch.setattr(scheduler_module, "run_historical_replay", fake_run_historical_replay)

    scheduler = EvaluationScheduler(
        reasoning_log=FakeReasoningLog(),
        price_feed=FakePriceFeed({"AAPL": 100.0}),
        replay_store=SimpleNamespace(),
        enabled=False,
        replay_enabled=True,
        replay_fixtures=("sample_fixture.json",),
        replay_provider_sets=("claude", "openai"),
        replay_bots=("analyst", "bear"),
        replay_execute_orders=False,
    )

    result = scheduler.run_replay_matrix_once()

    assert result["status"] == "succeeded"
    assert result["fixture_count"] == 1
    assert result["run_count"] == 2
    assert [call["providers"] for call in calls] == [("claude",), ("openai",)]
    assert all(call["bot_names"] == ("analyst", "bear") for call in calls)
    assert all(call["execute_orders"] is False for call in calls)
    assert calls[0]["config"]["source"] == "evaluation_scheduler"
    assert calls[0]["config"]["scheduled"] is True


def test_run_live_report_once_writes_monitoring_report(tmp_path):
    reasoning_log = FakeReasoningLog()
    scheduler = EvaluationScheduler(
        reasoning_log=reasoning_log,
        price_feed=FakePriceFeed({"AAPL": 110.0}),
        replay_store=SimpleNamespace(),
        enabled=False,
        live_report_dir=tmp_path,
        live_report_horizon="1h",
        live_report_min_samples=1,
    )

    result = scheduler.run_live_report_once()

    assert result["status"] == "succeeded"
    assert result["mode"] == "monitoring_only"
    assert result["decision_count"] == 1
    assert result["outcome_label_count"] == 0
    assert Path(result["json_path"]).exists()
    assert Path(result["markdown_path"]).exists()
    assert scheduler.status()["live_report"]["last_run"]["status"] == "succeeded"
