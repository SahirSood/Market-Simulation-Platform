import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import OrderDecision
from portfolio import FillRecord, Portfolio
from reasoning_log import ReasoningLog

SQLITE_URL = "sqlite:///:memory:"


def _make_bot(bot_id="bear-001", name="BearBot", llm_provider="claude"):
    bot = MagicMock()
    bot.bot_id = bot_id
    bot.name = name
    bot.llm_provider = llm_provider
    bot.portfolio = Portfolio(100_000)
    return bot


def _hold():
    return OrderDecision(
        action="HOLD",
        ticker=None,
        quantity=None,
        limit_price=None,
        reasoning="waiting",
        headline_used=None,
    )


def _buy():
    return OrderDecision(
        action="BUY",
        ticker="NVDA",
        quantity=50,
        limit_price=489.0,
        reasoning="Fed cut bullish",
        headline_used="Fed cuts rates",
    )


def _sell():
    return OrderDecision(
        action="SELL",
        ticker="NVDA",
        quantity=10,
        limit_price=500.0,
        reasoning="taking profit",
        headline_used=None,
    )


def test_reasoning_log_writes_and_reads_decision():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot()

    decision_id = log.log(bot, _buy(), fills=[FillRecord(1, "NVDA", "BUY", 50, 489.0)])

    records = log.get_decisions()
    assert decision_id == records[0]["id"]
    assert len(records) == 1
    record = records[0]
    assert record["bot_id"] == "bear-001"
    assert record["action"] == "BUY"
    assert record["ticker"] == "NVDA"
    assert record["quantity"] == 50
    assert record["fill_count"] == 1
    assert record["fill_qty_total"] == 50
    assert abs(record["fill_avg_price"] - 489.0) < 0.01
    assert record["llm_call_made"] is True
    assert "cash" in record["portfolio_snapshot"]


def test_reasoning_log_filters_by_bot_and_limit():
    log = ReasoningLog(database_url=SQLITE_URL)
    bear = _make_bot("bear-001", "BearBot")
    degen = _make_bot("degen-001", "DegenBot")

    for _ in range(3):
        log.log(bear, _hold(), fills=[])
    for _ in range(2):
        log.log(degen, _buy(), fills=[])

    assert len(log.get_decisions(bot_id="bear-001")) == 3
    assert len(log.get_decisions(bot_id="degen-001")) == 2
    assert len(log.get_decisions(limit=4)) == 4


def test_reasoning_log_writes_fallback_jsonl_on_db_failure(tmp_path, monkeypatch):
    import reasoning_log as reasoning_log_module
    from sqlalchemy.orm import Session

    fallback_path = tmp_path / "decisions_fallback.jsonl"
    monkeypatch.setattr(reasoning_log_module, "_FALLBACK_FILE", fallback_path)

    log = ReasoningLog(database_url=SQLITE_URL)
    with patch.object(Session, "commit", side_effect=Exception("DB down")):
        log.log(_make_bot(), _buy(), fills=[])

    lines = fallback_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["action"] == "BUY"
    assert parsed["bot_id"] == "bear-001"
    assert "cash" in parsed["portfolio_snapshot"]


def test_reasoning_log_portfolio_snapshot_and_weighted_average():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot()
    bot.portfolio.apply_fill(FillRecord(1, "AAPL", "BUY", 100, 150.0))

    fills = [
        FillRecord(2, "NVDA", "BUY", 100, 480.0),
        FillRecord(3, "NVDA", "BUY", 50, 490.0),
    ]
    log.log(bot, _buy(), fills=fills)

    record = log.get_decisions()[0]
    expected_avg = (100 * 480 + 50 * 490) / 150
    assert abs(record["fill_avg_price"] - expected_avg) < 0.01
    assert record["portfolio_snapshot"]["positions"]["AAPL"] == 100
    json.dumps(record["portfolio_snapshot"])


def test_reasoning_log_counts_only_billable_provider_calls():
    log = ReasoningLog(database_url=SQLITE_URL)
    claude = _make_bot("analyst-001", "AnalystBot", "claude")
    openai = _make_bot("macro-001", "MacroBot", "openai")
    no_call_hold = _hold()
    no_call_hold.llm_call_made = False
    no_call_hold.llm_estimated_cost_usd = 0.02
    buy = _buy()
    buy.llm_input_tokens = 1000
    buy.llm_output_tokens = 80
    buy.llm_total_tokens = 1080
    buy.llm_estimated_cost_usd = 0.02

    log.log(claude, buy, fills=[])
    log.log(openai, no_call_hold, fills=[])

    assert log.count_decisions() == 2
    assert log.count_decisions(billable_only=True) == 1
    assert log.count_decisions(llm_provider="claude", billable_only=True) == 1
    assert log.count_decisions(llm_provider="openai", billable_only=True) == 0
    assert log.sum_estimated_llm_cost(llm_provider="claude") == 0.02
    assert log.sum_estimated_llm_cost(llm_provider="openai") == 0.0


def test_reasoning_log_returns_filled_decisions_oldest_first():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot()

    log.log(bot, _buy(), fills=[FillRecord(1, "NVDA", "BUY", 50, 489.0)])
    log.log(bot, _hold(), fills=[])
    log.log(bot, _sell(), fills=[FillRecord(2, "NVDA", "SELL", 10, 500.0)])

    rows = log.get_filled_decisions("bear-001")

    assert [row["action"] for row in rows] == ["BUY", "SELL"]
    assert [row["fill_qty_total"] for row in rows] == [50, 10]
    assert rows[0]["fill_avg_price"] == 489.0


def test_reasoning_log_records_execution_order_and_fills():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot()
    decision = _buy()
    fill = FillRecord(42, "NVDA", "BUY", 50, 489.0)
    bot.portfolio.apply_fill(fill)

    decision_id = log.log(bot, decision, fills=[fill])
    execution_id = log.record_execution_order(
        bot,
        decision,
        engine_order_id=42,
        order_type="LIMIT",
        submitted_price=489.0,
        fills=[fill],
        decision_id=decision_id,
    )

    orders = log.get_execution_orders(filled_only=True)
    fills = log.get_execution_fills("bear-001")

    assert execution_id == orders[0]["id"]
    assert orders[0]["decision_id"] == decision_id
    assert orders[0]["status"] == "FILLED"
    assert orders[0]["fill_count"] == 1
    assert orders[0]["fill_qty_total"] == 50
    assert orders[0]["fill_avg_price"] == 489.0
    assert orders[0]["portfolio_snapshot"]["positions"] == {"NVDA": 50}
    assert fills == [
        {
            "id": fills[0]["id"],
            "execution_order_id": execution_id,
            "engine_order_id": 42,
            "timestamp": fills[0]["timestamp"],
            "bot_id": "bear-001",
            "ticker": "NVDA",
            "side": "BUY",
            "quantity": 50,
            "price": 489.0,
            "notional": 24450.0,
        }
    ]


def test_execution_orders_include_risk_rejections_without_fills():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot()
    decision = _buy()

    execution_id = log.record_execution_order(
        bot,
        decision,
        engine_order_id=None,
        order_type="LIMIT",
        submitted_price=489.0,
        fills=[],
        status="REJECTED",
        rejection_reason="ticker outside tradable universe",
    )

    orders = log.get_execution_orders(status="REJECTED")

    assert execution_id == orders[0]["id"]
    assert orders[0]["rejection_reason"] == "ticker outside tradable universe"
    assert orders[0]["fill_count"] == 0
    assert log.get_execution_orders(filled_only=True) == []


def test_reasoning_log_records_agent_activity_events():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot("analyst-001", "AnalystBot", "openai")

    activity_id = log.record_agent_activity(
        bot=bot,
        event_type="tool",
        stage="rag_retrieval",
        tool_name="retrieve_evidence",
        status="succeeded",
        summary="Retrieved 2 evidence chunks",
        duration_ms=12.34567,
        evidence_ids=[7, "8", "bad"],
        metadata={"top_k": 2, "nested": {"ok": True}},
    )

    rows = log.get_agent_activity(bot_id="analyst-001")

    assert activity_id == rows[0]["id"]
    assert rows[0]["bot_name"] == "AnalystBot"
    assert rows[0]["llm_provider"] == "openai"
    assert rows[0]["event_type"] == "tool"
    assert rows[0]["stage"] == "rag_retrieval"
    assert rows[0]["tool_name"] == "retrieve_evidence"
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["duration_ms"] == 12.346
    assert rows[0]["evidence_ids"] == [7, 8]
    assert rows[0]["metadata"]["nested"]["ok"] is True
