import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import OrderDecision
from portfolio import FillRecord, Portfolio
from reasoning_log import ReasoningLog

SQLITE_URL = "sqlite:///:memory:"


def _make_bot(bot_id="bear-001", name="BearBot"):
    bot = MagicMock()
    bot.bot_id = bot_id
    bot.name = name
    bot.llm_provider = "claude"
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


def test_reasoning_log_writes_and_reads_decision():
    log = ReasoningLog(database_url=SQLITE_URL)
    bot = _make_bot()

    log.log(bot, _buy(), fills=[FillRecord(1, "NVDA", "BUY", 50, 489.0)])

    records = log.get_decisions()
    assert len(records) == 1
    record = records[0]
    assert record["bot_id"] == "bear-001"
    assert record["action"] == "BUY"
    assert record["ticker"] == "NVDA"
    assert record["quantity"] == 50
    assert record["fill_count"] == 1
    assert record["fill_qty_total"] == 50
    assert abs(record["fill_avg_price"] - 489.0) < 0.01
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
