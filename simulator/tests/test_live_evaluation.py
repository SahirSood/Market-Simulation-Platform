import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from live_evaluation import (
    build_live_evaluation_report,
    generate_live_evaluation_report,
    write_live_evaluation_report,
)


NOW = datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=7)


def _decision(
    decision_id,
    *,
    action="BUY",
    provider="openai",
    bot_id="analyst-001-openai",
    ticker="NVDA",
    prompt_version="competitive-v2",
    hold_cause=None,
    cost=0.02,
):
    return {
        "id": decision_id,
        "timestamp": NOW - timedelta(hours=decision_id),
        "bot_id": bot_id,
        "bot_name": bot_id.replace("-001", "").title(),
        "llm_provider": provider,
        "action": action,
        "hold_cause": hold_cause,
        "ticker": ticker,
        "quantity": 10 if action != "HOLD" else None,
        "confidence": 0.7,
        "evidence_ids": [decision_id] if action != "HOLD" else [],
        "evidence_urls": [],
        "speculative": False,
        "llm_call_made": True,
        "llm_estimated_cost_usd": cost,
        "model_metadata": {
            "prompt_version": prompt_version,
            "model": "gpt-test",
        },
        "fill_qty_total": 10 if action != "HOLD" else 0,
        "fill_avg_price": 100.0 if action != "HOLD" else None,
    }


def _outcome(decision_id, *, status="profitable", provider="openai", bot_id="analyst-001-openai"):
    return {
        "id": decision_id + 100,
        "decision_id": decision_id,
        "bot_id": bot_id,
        "bot_name": bot_id.replace("-001", "").title(),
        "llm_provider": provider,
        "decision_timestamp": NOW - timedelta(hours=decision_id),
        "horizon": "1d",
        "observed_at": NOW - timedelta(hours=decision_id) + timedelta(minutes=1),
        "action": "BUY",
        "ticker": "NVDA",
        "entry_price": 100.0,
        "position_pnl": 10.0 if status == "profitable" else -10.0,
        "portfolio_delta": 10.0 if status == "profitable" else -10.0,
        "llm_estimated_cost_usd": 0.02,
        "net_after_llm_cost": 9.98 if status == "profitable" else -10.02,
        "filled_quantity": 10,
        "risk_approved": True,
        "outcome_status": status,
        "metadata": {},
    }


def test_report_is_monitoring_only_until_selected_horizon_has_enough_labels():
    report = build_live_evaluation_report(
        [_decision(1, action="HOLD", hold_cause="no_edge")],
        [_outcome(1, status="no_trade")],
        since=SINCE,
        until=NOW,
        min_samples=2,
        generated_at=NOW,
    )

    assert report["mode"] == "monitoring_only"
    assert report["sample"]["labeled_decision_count"] == 1
    assert report["sample"]["remaining_labels_needed"] == 1
    assert report["prompt_versions"]["competitive-v2"]["hold_count"] == 1
    assert report["benchmark_comparison"]["available"] is False
    assert "Monitoring only" in report["conclusion"]["message"]


def test_report_combines_bot_provider_prompt_cost_and_risk_readouts():
    decisions = [
        _decision(1),
        _decision(2, provider="claude", bot_id="macro-001-claude", prompt_version="focused-v3"),
        _decision(3, action="HOLD", hold_cause="risk_limit", bot_id="bear-001-openai"),
    ]
    outcomes = [
        _outcome(1),
        _outcome(2, status="unprofitable", provider="claude", bot_id="macro-001-claude"),
        {
            **_outcome(3, status="risk_rejected", bot_id="bear-001-openai"),
            "risk_approved": False,
            "action": "SELL",
            "metadata": {"risk_reason": "short selling disabled"},
        },
    ]

    report = build_live_evaluation_report(
        decisions,
        outcomes,
        since=SINCE,
        until=NOW,
        min_samples=3,
        generated_at=NOW,
    )

    assert report["mode"] == "decision_grade"
    assert report["sample"]["sample_sufficient"] is True
    assert set(report["by_provider"]) == {"claude", "openai"}
    assert report["by_bot"]["macro-001-claude"]["outcomes"]["unprofitable_count"] == 1
    assert set(report["prompt_versions"]) == {"competitive-v2", "focused-v3"}
    assert report["costs"]["total_estimated_cost_usd"] == 0.06
    assert report["risk_blocked"]["blocked_count"] == 1
    assert report["risk_blocked"]["available"] is False


def test_generate_and_write_report_are_no_llm_and_json_safe(tmp_path):
    class FakeReasoningLog:
        def get_decisions(self, **kwargs):
            return [_decision(1)]

        def get_decision_outcomes(self, **kwargs):
            return [_outcome(1)]

    report = generate_live_evaluation_report(
        FakeReasoningLog(),
        since=SINCE,
        until=NOW,
        min_samples=1,
        now=NOW,
    )
    paths = write_live_evaluation_report(report, tmp_path, basename="weekly")

    assert report["mode"] == "decision_grade"
    assert "markdown" in report
    assert paths["json_path"].endswith("weekly.json")
    assert paths["markdown_path"].endswith("weekly.md")
    assert '"report_type": "live_evaluation"' in open(paths["json_path"], encoding="utf-8").read()
    assert "# Live Evaluation Report" in open(paths["markdown_path"], encoding="utf-8").read()


def test_report_calculates_benchmark_excess_return_when_snapshots_exist():
    report = build_live_evaluation_report(
        [_decision(1)],
        [{
            **_outcome(1),
            "metadata": {
                "benchmark_returns": {
                    "SPY": {"start_price": 100.0, "end_price": 100.0, "return": 0.0},
                    "QQQ": {"start_price": 100.0, "end_price": 102.0, "return": 0.02},
                }
            },
        }],
        since=SINCE,
        until=NOW,
        min_samples=1,
        generated_at=NOW,
    )

    comparison = report["benchmark_comparison"]
    assert comparison["available"] is True
    assert comparison["status"] == "available"
    assert comparison["by_benchmark"]["SPY"]["beat_count"] == 1
    assert comparison["by_benchmark"]["QQQ"]["lag_count"] == 1
    assert comparison["by_benchmark"]["SPY"]["avg_excess_return"] == 0.01
