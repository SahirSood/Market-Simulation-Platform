import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from outcomes import evaluate_due_outcomes, summarize_outcomes


class FakePriceFeed:
    def __init__(self, prices):
        self.prices = prices

    def get_price(self, ticker):
        return self.prices[ticker]


class FakeReasoningLog:
    def __init__(self, decisions, outcomes):
        self.decisions = decisions
        self.outcomes = list(outcomes)
        self.recorded = []

    def get_decisions(self, limit=1000, **kwargs):
        return self.decisions[:limit]

    def get_decision_outcomes(self, limit=1000, **kwargs):
        return self.outcomes[:limit]

    def record_decision_outcome(self, **payload):
        self.recorded.append(payload)
        self.outcomes.append({**payload, "id": len(self.outcomes) + 1})
        return len(self.outcomes)


def test_evaluate_due_outcomes_labels_profitable_buy_after_horizon():
    now = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    decision = {
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
        "portfolio_snapshot": {"cash": 99_000, "positions": {"AAPL": 10}, "cost_basis": {"AAPL": 100}, "total_value": 100_000},
    }
    immediate = {
        "decision_id": 1,
        "horizon": "immediate",
        "action": "BUY",
        "ticker": "AAPL",
        "entry_price": 100.0,
        "filled_quantity": 10,
        "risk_approved": True,
        "outcome_status": "filled",
        "portfolio_value_at_decision": 100_000.0,
        "llm_estimated_cost_usd": 0.02,
        "metadata": {
            "benchmark_prices_at_decision": {
                "SPY": 100.0,
                "QQQ": 200.0,
            }
        },
    }
    log = FakeReasoningLog([decision], [immediate])

    result = evaluate_due_outcomes(
        log,
        FakePriceFeed({"AAPL": 110.0, "SPY": 105.0, "QQQ": 210.0}),
        horizons=["1h"],
        now=now,
    )

    assert result["created_count"] == 1
    recorded = log.recorded[0]
    assert recorded["horizon"] == "1h"
    assert recorded["outcome_status"] == "profitable"
    assert recorded["position_pnl"] == 100.0
    assert recorded["portfolio_value_at_observation"] == 100_100.0
    assert recorded["net_after_llm_cost"] == 99.98
    assert recorded["metadata"]["benchmark_returns"]["SPY"]["return"] == 0.05


def test_evaluate_due_outcomes_labels_profitable_short():
    now = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    decision = {
        "id": 2,
        "timestamp": now - timedelta(hours=2),
        "bot_id": "bear-001",
        "bot_name": "BearBot",
        "llm_provider": "openai",
        "action": "SELL",
        "ticker": "NVDA",
        "quantity": 5,
        "fill_qty_total": 5,
        "fill_avg_price": 200.0,
        "llm_estimated_cost_usd": 0.01,
        "portfolio_snapshot": {"cash": 101_000, "positions": {"NVDA": -5}, "cost_basis": {"NVDA": 200}, "total_value": 100_000},
    }
    immediate = {
        "decision_id": 2,
        "horizon": "immediate",
        "action": "SELL",
        "ticker": "NVDA",
        "entry_price": 200.0,
        "filled_quantity": 5,
        "risk_approved": True,
        "outcome_status": "filled",
        "portfolio_value_at_decision": 100_000.0,
        "llm_estimated_cost_usd": 0.01,
    }
    log = FakeReasoningLog([decision], [immediate])

    result = evaluate_due_outcomes(
        log,
        FakePriceFeed({"NVDA": 190.0}),
        horizons=["1h"],
        now=now,
    )

    assert result["created_count"] == 1
    assert log.recorded[0]["outcome_status"] == "profitable"
    assert log.recorded[0]["position_pnl"] == 50.0


def test_summarize_outcomes_tracks_cost_and_win_rate():
    summary = summarize_outcomes([
        {
            "bot_id": "analyst-001",
            "bot_name": "AnalystBot",
            "llm_provider": "claude",
            "horizon": "1h",
            "outcome_status": "profitable",
            "position_pnl": 100.0,
            "net_after_llm_cost": 99.98,
            "llm_estimated_cost_usd": 0.02,
        },
        {
            "bot_id": "bear-001",
            "bot_name": "BearBot",
            "llm_provider": "openai",
            "horizon": "1h",
            "outcome_status": "unprofitable",
            "position_pnl": -10.0,
            "net_after_llm_cost": -10.01,
            "llm_estimated_cost_usd": 0.01,
        },
        {
            "bot_id": "macro-001",
            "bot_name": "MacroBot",
            "llm_provider": "claude",
            "horizon": "1h",
            "outcome_status": "risk_rejected",
            "position_pnl": 0.0,
            "net_after_llm_cost": -0.02,
            "llm_estimated_cost_usd": 0.02,
        },
    ])

    totals = summary["totals"]
    assert totals["outcome_count"] == 3
    assert totals["evaluated_trade_count"] == 2
    assert totals["win_rate"] == 0.5
    assert totals["total_position_pnl"] == 90.0
    assert totals["total_llm_estimated_cost_usd"] == 0.05
    assert summary["by_provider"]["claude"]["outcome_count"] == 2
