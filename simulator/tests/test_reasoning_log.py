"""
Run from the simulator/ directory:
    python tests/test_reasoning_log.py

Uses SQLite in-memory so no Postgres is needed.
"""
import sys
import os
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reasoning_log import ReasoningLog
from base_bot import OrderDecision
from portfolio import FillRecord, Portfolio

_SQLITE_URL = "sqlite:///:memory:"


def _make_bot(bot_id="bear-001", name="BearBot"):
    bot = MagicMock()
    bot.bot_id       = bot_id
    bot.name         = name
    bot.llm_provider = "claude"
    bot.portfolio    = Portfolio(100_000)
    return bot

def _hold():
    return OrderDecision(action="HOLD", ticker=None, quantity=None,
                         limit_price=None, reasoning="waiting", headline_used=None)

def _buy():
    return OrderDecision(action="BUY", ticker="NVDA", quantity=50,
                         limit_price=489.0, reasoning="Fed cut bullish",
                         headline_used="Fed cuts rates")


# ── Test 1: write and read back a single record ───────────────────────────────

print("=" * 60)
print("Test 1: Write a record and read it back")
print("=" * 60)
log = ReasoningLog(database_url=_SQLITE_URL)
bot = _make_bot()
log.log(bot, _buy(), fills=[FillRecord(1, "NVDA", "BUY", 50, 489.0)])
records = log.get_decisions()
assert len(records) == 1
r = records[0]
assert r.bot_id       == "bear-001"
assert r.action       == "BUY"
assert r.ticker       == "NVDA"
assert r.quantity     == 50
assert r.fill_count   == 1
assert r.fill_qty_total == 50
assert abs(r.fill_avg_price - 489.0) < 0.01
assert "cash" in r.portfolio_snapshot
print(f"  PASS — record: {r.action} {r.quantity} {r.ticker} @ {r.limit_price}")


# ── Test 2: filter by bot_id ──────────────────────────────────────────────────

print()
print("=" * 60)
print("Test 2: Filter by bot_id")
print("=" * 60)
log2 = ReasoningLog(database_url=_SQLITE_URL)
bear = _make_bot("bear-001", "BearBot")
degen = _make_bot("degen-001", "DegenBot")
for _ in range(3):
    log2.log(bear, _hold(), fills=[])
for _ in range(2):
    log2.log(degen, _buy(), fills=[])

bear_records = log2.get_decisions(bot_id="bear-001")
degen_records = log2.get_decisions(bot_id="degen-001")
assert len(bear_records) == 3, f"Expected 3, got {len(bear_records)}"
assert len(degen_records) == 2, f"Expected 2, got {len(degen_records)}"
print(f"  PASS — bear={len(bear_records)}, degen={len(degen_records)}")


# ── Test 3: limit parameter ───────────────────────────────────────────────────

print()
print("=" * 60)
print("Test 3: limit parameter")
print("=" * 60)
log3 = ReasoningLog(database_url=_SQLITE_URL)
for i in range(10):
    log3.log(_make_bot(), _hold(), fills=[])
results = log3.get_decisions(limit=4)
assert len(results) == 4, f"Expected 4, got {len(results)}"
print(f"  PASS — limit=4 returned {len(results)} records")


# ── Test 4: DB failure → fallback JSONL written ───────────────────────────────

print()
print("=" * 60)
print("Test 4: DB failure triggers fallback JSONL write")
print("=" * 60)
import tempfile
from pathlib import Path
import reasoning_log as rl_module

with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tmp:
    fallback_path = Path(tmp.name)

original_path = rl_module._FALLBACK_FILE
rl_module._FALLBACK_FILE = fallback_path

log4 = ReasoningLog(database_url=_SQLITE_URL)
# Patch Session to raise so DB write fails
from sqlalchemy.orm import Session as _Session
with patch.object(_Session, "commit", side_effect=Exception("DB down")):
    log4.log(_make_bot(), _buy(), fills=[])

# Check fallback file has a valid JSON line
lines = fallback_path.read_text().strip().splitlines()
assert len(lines) >= 1, "Expected at least one fallback line"
parsed = json.loads(lines[0])
assert parsed["action"]  == "BUY"
assert parsed["bot_id"]  == "bear-001"
assert "cash" in parsed["portfolio_snapshot"]
print(f"  PASS — fallback line written: {lines[0][:80]}...")

rl_module._FALLBACK_FILE = original_path
fallback_path.unlink(missing_ok=True)


# ── Test 5: portfolio_snapshot is JSON-serializable ───────────────────────────

print()
print("=" * 60)
print("Test 5: portfolio_snapshot round-trips through JSON")
print("=" * 60)
log5 = ReasoningLog(database_url=_SQLITE_URL)
bot5 = _make_bot()
from portfolio import FillRecord
bot5.portfolio.apply_fill(FillRecord(1, "AAPL", "BUY", 100, 150.0))
log5.log(bot5, _hold(), fills=[])
r5 = log5.get_decisions()[0]
snap = r5.portfolio_snapshot
assert snap["positions"]["AAPL"] == 100
assert snap["cash"] == 100_000 - 15_000
json_str = json.dumps(snap)   # must not raise
print(f"  PASS — snapshot JSON-serializable: {json_str[:80]}...")


# ── Test 6: fill_avg_price weighted average ───────────────────────────────────

print()
print("=" * 60)
print("Test 6: fill_avg_price is weighted average of fills")
print("=" * 60)
log6 = ReasoningLog(database_url=_SQLITE_URL)
fills = [
    FillRecord(1, "NVDA", "BUY", 100, 480.0),
    FillRecord(2, "NVDA", "BUY",  50, 490.0),
]
log6.log(_make_bot(), _buy(), fills=fills)
r6 = log6.get_decisions()[0]
expected_avg = (100 * 480 + 50 * 490) / 150
assert abs(r6.fill_avg_price - expected_avg) < 0.01, f"Expected {expected_avg}, got {r6.fill_avg_price}"
print(f"  PASS — fill_avg_price={r6.fill_avg_price:.2f} (expected {expected_avg:.2f})")


print()
print("All ReasoningLog tests passed.")
