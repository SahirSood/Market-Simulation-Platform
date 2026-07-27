import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api import state as app_state
from api.routers.market import _snapshot_to_model, get_trades


def test_order_book_snapshot_exposes_aggregated_order_counts():
    snapshot = SimpleNamespace(
        bids=[SimpleNamespace(price=99.5, total_quantity=500, order_count=1)],
        asks=[SimpleNamespace(price=100.5, total_quantity=750, order_count=3)],
        spread=1.0,
        mid_price=100.0,
    )

    result = _snapshot_to_model("AAPL", snapshot, trade_count=4)

    assert result.bids[0].quantity == 500
    assert result.bids[0].order_count == 1
    assert result.asks[0].quantity == 750
    assert result.asks[0].order_count == 3
    assert result.trade_count == 4


def test_get_trades_uses_execution_ledger_fills() -> None:
    timestamp = datetime(2026, 7, 22, tzinfo=timezone.utc)

    class Log:
        def get_execution_orders(self, bot_id=None, status=None, limit=100, filled_only=False):
            assert bot_id is None
            assert status is None
            assert limit == 50
            assert filled_only is True
            return [
                {
                    "id": 12,
                    "timestamp": timestamp,
                    "bot_id": "analyst-001-claude",
                    "bot_name": "AnalystBot (Claude)",
                    "action": "BUY",
                    "ticker": "AAPL",
                    "quantity": 20,
                    "fill_avg_price": 210.0,
                    "fill_qty_total": 20,
                    "reasoning": "validated evidence-backed buy",
                }
            ]

        def get_decisions(self, *args, **kwargs):
            raise AssertionError("decision fallback should not be used")

    app_state.init(SimpleNamespace(reasoning_log=Log()))

    trades = asyncio.run(get_trades())

    assert len(trades) == 1
    assert trades[0].id == 12
    assert trades[0].ticker == "AAPL"
    assert trades[0].fill_qty_total == 20


def test_get_trades_falls_back_to_filled_decisions_when_ledger_empty() -> None:
    timestamp = datetime(2026, 7, 22, tzinfo=timezone.utc)

    class Log:
        def get_execution_orders(self, bot_id=None, status=None, limit=100, filled_only=False):
            return []

        def get_decisions(self, bot_id=None, action=None, limit=100):
            assert limit == 50
            return [
                {
                    "id": 20,
                    "timestamp": timestamp,
                    "bot_id": "macro-001-openai",
                    "bot_name": "MacroBot (OpenAI)",
                    "action": "SELL",
                    "ticker": "SPY",
                    "quantity": 5,
                    "fill_avg_price": 510.0,
                    "fill_qty_total": 5,
                    "reasoning": "older filled decision",
                },
                {
                    "id": 21,
                    "timestamp": timestamp,
                    "bot_id": "macro-001-openai",
                    "bot_name": "MacroBot (OpenAI)",
                    "action": "HOLD",
                    "ticker": None,
                    "quantity": None,
                    "fill_avg_price": None,
                    "fill_qty_total": 0,
                    "reasoning": "not a trade",
                },
            ]

    app_state.init(SimpleNamespace(reasoning_log=Log()))

    trades = asyncio.run(get_trades())

    assert len(trades) == 1
    assert trades[0].id == 20
    assert trades[0].action == "SELL"
