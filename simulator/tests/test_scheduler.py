"""
Run from the simulator/ directory:
    python tests/test_scheduler.py
"""
import sys
import os
import time
import threading
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler import BotScheduler
from base_bot import OrderDecision
from portfolio import FillRecord


def _hold_decision():
    return OrderDecision(action="HOLD", ticker=None, quantity=None,
                         limit_price=None, reasoning="test hold", headline_used=None)

def _buy_decision():
    return OrderDecision(action="BUY", ticker="AAPL", quantity=100,
                         limit_price=150.0, reasoning="bullish", headline_used="headline")

def _make_bot(name, decision):
    bot = MagicMock()
    bot.name         = name
    bot.bot_id       = f"{name.lower()}-001"
    bot.decide.return_value = decision
    bot.price_feed.get_price.return_value = 150.0
    bot.portfolio    = MagicMock()
    return bot

def _make_scheduler(bots, reasoning_log=None):
    noise_pool     = MagicMock()
    noise_pool.trader_count = 10
    engine_adapter = MagicMock()
    engine_adapter.submit.return_value = (1, [])
    return (
        BotScheduler(bots, noise_pool, engine_adapter, reasoning_log),
        noise_pool,
        engine_adapter,
    )


# ── Test 1: HOLD → reasoning_log.log called, engine not touched ──────────────

print("=" * 60)
print("Test 1: HOLD decision — log called, engine NOT called")
print("=" * 60)
reasoning_log = MagicMock()
bot = _make_bot("BearBot", _hold_decision())
scheduler, _, engine_adapter = _make_scheduler([bot], reasoning_log)

scheduler._run_bot(bot)

assert engine_adapter.submit.call_count == 0
reasoning_log.log.assert_called_once()
args = reasoning_log.log.call_args
assert args[0][2] == []   # fills=[]
print(f"  PASS — engine not called, log called with fills=[]")


# ── Test 2: BUY → engine.submit called with correct args ─────────────────────

print()
print("=" * 60)
print("Test 2: BUY decision — engine.submit called correctly")
print("=" * 60)
reasoning_log2 = MagicMock()
bot2 = _make_bot("DegenBot", _buy_decision())
scheduler2, _, engine2 = _make_scheduler([bot2], reasoning_log2)

scheduler2._run_bot(bot2)

engine2.submit.assert_called_once()
call_kwargs = engine2.submit.call_args.kwargs
assert call_kwargs["ticker"]     == "AAPL"
assert call_kwargs["side"]       == "BUY"
assert call_kwargs["order_type"] == "LIMIT"
assert call_kwargs["price"]      == 150.0
assert call_kwargs["quantity"]   == 100
print(f"  PASS — submit called: {call_kwargs}")


# ── Test 3: fills forwarded to portfolio.apply_fill ───────────────────────────

print()
print("=" * 60)
print("Test 3: Fills from engine forwarded to portfolio.apply_fill")
print("=" * 60)
fill = FillRecord(order_id=1, ticker="AAPL", side="BUY", quantity=100, price=150.0)
bot3 = _make_bot("AnalystBot", _buy_decision())
noise = MagicMock(); noise.trader_count = 10
engine3 = MagicMock()
engine3.submit.return_value = (1, [fill])
log3 = MagicMock()
sched3 = BotScheduler([bot3], noise, engine3, log3)

sched3._run_bot(bot3)

bot3.portfolio.apply_fill.assert_called_once_with(fill, strict=False)
print(f"  PASS — apply_fill called with the fill from engine")


# ── Test 4: bot exception does not crash scheduler ───────────────────────────

print()
print("=" * 60)
print("Test 4: Bot exception — scheduler continues, no propagation")
print("=" * 60)
crash_bot = MagicMock()
crash_bot.name   = "CrashBot"
crash_bot.bot_id = "crash-001"
crash_bot.decide.side_effect = RuntimeError("LLM on fire")
ok_bot = _make_bot("OkBot", _hold_decision())

sched4, _, _ = _make_scheduler([crash_bot, ok_bot])
# Neither call should raise
sched4._run_bot(crash_bot)
sched4._run_bot(ok_bot)
print(f"  PASS — CrashBot exception swallowed, OkBot ran fine")


# ── Test 5: noise traders fire on start ───────────────────────────────────────

print()
print("=" * 60)
print("Test 5: Noise pool ticked on scheduler start")
print("=" * 60)
bot5 = _make_bot("BearBot", _hold_decision())
noise5 = MagicMock(); noise5.trader_count = 10
engine5 = MagicMock(); engine5.submit.return_value = (1, [])
sched5 = BotScheduler([bot5], noise5, engine5, None)
sched5.start()
time.sleep(0.1)   # let the immediate noise tick run
sched5.stop()
assert noise5.tick.call_count >= 1, f"Expected at least 1 noise tick, got {noise5.tick.call_count}"
print(f"  PASS — noise tick called {noise5.tick.call_count} time(s)")


# ── Test 6: market order when limit_price is None ────────────────────────────

print()
print("=" * 60)
print("Test 6: MARKET order when limit_price=None")
print("=" * 60)
market_decision = OrderDecision(
    action="BUY", ticker="NVDA", quantity=50, limit_price=None,
    reasoning="YOLO", headline_used=None,
)
bot6 = _make_bot("DegenBot", market_decision)
bot6.price_feed.get_price.return_value = 489.0
sched6, _, engine6 = _make_scheduler([bot6])
sched6._run_bot(bot6)
call6 = engine6.submit.call_args.kwargs
assert call6["order_type"] == "MARKET"
assert call6["price"]      == 489.0   # from price_feed fallback
print(f"  PASS — MARKET order @ {call6['price']}")


print()
print("All scheduler tests passed.")
