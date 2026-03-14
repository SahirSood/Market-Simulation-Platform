"""
Run from the simulator/ directory:
    python tests/test_noise_traders.py
"""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noise_traders import RandomTrader, NoiseTraderPool, NoiseConfig


class _MockPriceFeed:
    def get_price(self, ticker): return 150.0
    def get_active_tickers(self): return ["AAPL", "NVDA", "MSFT"]


def _make_adapter():
    adapter = MagicMock()
    adapter.submit.return_value = (1, [])
    adapter.cancel.return_value = True
    return adapter


# ── Test 1: tick() calls submit() once per trader ────────────────────────────

print("=" * 60)
print("Test 1: tick() calls submit() once per trader")
print("=" * 60)
adapter = _make_adapter()
pool = NoiseTraderPool(_MockPriceFeed(), adapter, n_traders=10)
pool.tick()
assert adapter.submit.call_count == 10, f"Expected 10 submits, got {adapter.submit.call_count}"
print(f"  PASS — {adapter.submit.call_count} submit calls for 10 traders")


# ── Test 2: price feed error does not crash pool ──────────────────────────────

print()
print("=" * 60)
print("Test 2: Price feed error does not crash pool")
print("=" * 60)

class _FailingPriceFeed:
    def get_price(self, ticker): raise ConnectionError("yfinance down")
    def get_active_tickers(self): return ["AAPL"]

adapter2 = _make_adapter()
pool2 = NoiseTraderPool(_FailingPriceFeed(), adapter2, n_traders=3)
pool2.tick()   # must not raise
assert adapter2.submit.call_count == 0   # no submits if price fetch fails
print(f"  PASS — no crash, {adapter2.submit.call_count} submits")


# ── Test 3: cancel called when active_order_id set and random < cancel_prob ──

print()
print("=" * 60)
print("Test 3: Previous order cancelled when random() < cancel_prob")
print("=" * 60)
adapter3 = _make_adapter()
adapter3.submit.return_value = (42, [])
trader = RandomTrader(0, _MockPriceFeed(), adapter3, NoiseConfig(cancel_prob=1.0))

# First act — no active order to cancel
trader.act()
assert adapter3.cancel.call_count == 0
assert trader._active_order_id == 42

# Second act — cancel_prob=1.0 means always cancel
trader.act()
adapter3.cancel.assert_called_with(42)
print(f"  PASS — previous order 42 was cancelled before new order")


# ── Test 4: cancel NOT called when random() > cancel_prob ────────────────────

print()
print("=" * 60)
print("Test 4: Previous order not cancelled when random() > cancel_prob")
print("=" * 60)
adapter4 = _make_adapter()
adapter4.submit.return_value = (99, [])
trader2 = RandomTrader(1, _MockPriceFeed(), adapter4, NoiseConfig(cancel_prob=0.0))
trader2.act()
trader2.act()  # cancel_prob=0.0 → never cancel
assert adapter4.cancel.call_count == 0
print(f"  PASS — cancel not called (cancel_prob=0.0)")


# ── Test 5: side is sometimes BUY, sometimes SELL (over 50 acts) ─────────────

print()
print("=" * 60)
print("Test 5: Both BUY and SELL orders generated over 50 acts")
print("=" * 60)
adapter5 = _make_adapter()
sides_seen = set()
call_num = [0]

def capture_side(**kwargs):
    sides_seen.add(kwargs["side"])
    call_num[0] += 1
    return (call_num[0], [])

adapter5.submit.side_effect = lambda **kw: capture_side(**kw)
trader3 = RandomTrader(2, _MockPriceFeed(), adapter5)
for _ in range(50):
    trader3.act()

assert "BUY"  in sides_seen, "Expected at least one BUY"
assert "SELL" in sides_seen, "Expected at least one SELL"
print(f"  PASS — both sides seen over 50 acts")


# ── Test 6: tickers drawn from price feed active_tickers ─────────────────────

print()
print("=" * 60)
print("Test 6: Noise traders use price_feed.get_active_tickers()")
print("=" * 60)

class _SpecificTickerFeed:
    def get_price(self, ticker): return 200.0
    def get_active_tickers(self): return ["ONLY_THIS"]

adapter6 = _make_adapter()
adapter6.submit.return_value = (1, [])
trader4 = RandomTrader(3, _SpecificTickerFeed(), adapter6)
for _ in range(10):
    trader4.act()

tickers_used = {call.kwargs["ticker"] for call in adapter6.submit.call_args_list}
assert tickers_used == {"ONLY_THIS"}, f"Expected only ONLY_THIS, got {tickers_used}"
print(f"  PASS — all orders used ticker from get_active_tickers()")


# ── Test 7: pool tick() errors don't stop other traders ──────────────────────

print()
print("=" * 60)
print("Test 7: One trader crashing doesn't stop others in tick()")
print("=" * 60)
adapter7 = _make_adapter()
call_counts = [0, 0, 0]

class _MixedAdapter:
    def submit(self, **kw):
        trader_id = int(kw["bot_id"].split("-")[1])
        call_counts[trader_id] += 1
        if trader_id == 1:
            raise RuntimeError("Trader 1 crashes")
        return (trader_id * 10, [])
    def cancel(self, order_id): return True

pool3 = NoiseTraderPool(_MockPriceFeed(), _MixedAdapter(), n_traders=3)
pool3.tick()   # must not raise even though trader 1 crashes
assert call_counts[0] >= 1 or call_counts[2] >= 1, "At least traders 0 and 2 should have acted"
print(f"  PASS — tick() completed despite trader 1 crash")


print()
print("All noise trader tests passed.")
