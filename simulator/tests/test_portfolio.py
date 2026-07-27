"""
Run from the simulator/ directory:
    python tests/test_portfolio.py
"""
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio import Portfolio, FillRecord

STARTING = 100_000.0


class _MockPriceFeed:
    def __init__(self, prices: dict):
        self._prices = prices
    def get_price(self, ticker):
        return self._prices[ticker]


def _fill(ticker, side, qty, price, order_id=1):
    return FillRecord(order_id=order_id, ticker=ticker, side=side,
                      quantity=qty, price=price)


# ── Test 1: BUY reduces cash and increases position ───────────────────────────

print("=" * 60)
print("Test 1: BUY 100 AAPL @ $150")
print("=" * 60)
p = Portfolio(STARTING)
p.apply_fill(_fill("AAPL", "BUY", 100, 150.0))
assert p.cash == STARTING - 15_000.0, f"Expected {STARTING-15000}, got {p.cash}"
assert p.positions["AAPL"] == 100
assert abs(p._cost_basis["AAPL"] - 150.0) < 0.001
print(f"  PASS — cash={p.cash:,.2f}, AAPL={p.positions['AAPL']}, basis={p._cost_basis['AAPL']}")


# ── Test 2: SELL reduces position and increases cash ──────────────────────────

print()
print("=" * 60)
print("Test 2: SELL 50 AAPL @ $155")
print("=" * 60)
p.apply_fill(_fill("AAPL", "SELL", 50, 155.0, order_id=2))
expected_cash = STARTING - 15_000.0 + 50 * 155.0
assert abs(p.cash - expected_cash) < 0.01, f"Expected {expected_cash}, got {p.cash}"
assert p.positions["AAPL"] == 50
print(f"  PASS — cash={p.cash:,.2f}, AAPL remaining={p.positions['AAPL']}")


# ── Test 3: Sell all shares clears position and cost_basis ────────────────────

print()
print("=" * 60)
print("Test 3: Sell remaining 50 AAPL — position cleared")
print("=" * 60)
p.apply_fill(_fill("AAPL", "SELL", 50, 160.0, order_id=3))
assert "AAPL" not in p.positions
assert "AAPL" not in p._cost_basis
print(f"  PASS — AAPL removed from positions and cost_basis")


# ── Test 4: Overdraft raises ValueError (strict=True) ─────────────────────────

print()
print("=" * 60)
print("Test 4: Overdraft raises ValueError (strict=True)")
print("=" * 60)
p2 = Portfolio(1_000.0)   # only $1k
try:
    p2.apply_fill(_fill("NVDA", "BUY", 100, 489.0))
    print("  FAIL — should have raised ValueError")
except ValueError as e:
    print(f"  PASS — ValueError: {e}")


# ── Test 5: Overdraft with strict=False logs warning, does not raise ──────────

print()
print("=" * 60)
print("Test 5: Overdraft with strict=False — no exception")
print("=" * 60)
p3 = Portfolio(1_000.0)
p3.apply_fill(_fill("NVDA", "BUY", 100, 489.0), strict=False)
print(f"  PASS — applied anyway, cash={p3.cash:,.2f}")


# ── Test 6: Short sell raises ValueError (strict=True) ───────────────────────

print()
print("=" * 60)
print("Test 6: Selling more than held raises ValueError")
print("=" * 60)
p4 = Portfolio(STARTING)
p4.apply_fill(_fill("AAPL", "BUY", 50, 150.0))
try:
    p4.apply_fill(_fill("AAPL", "SELL", 100, 155.0))  # only have 50
    print("  FAIL — should have raised ValueError")
except ValueError as e:
    print(f"  PASS — ValueError: {e}")


# ── Test 7: mark_to_market ───────────────────────────────────────────────────

print()
print("=" * 60)
print("Test 7: mark_to_market")
print("=" * 60)
p5 = Portfolio(STARTING)
p5.apply_fill(_fill("AAPL", "BUY", 100, 150.0))
# Cash: 100k - 15k = 85k. 100 shares now worth $160 each = $16k. Total = $101k.
mtm = p5.mark_to_market(_MockPriceFeed({"AAPL": 160.0}))
assert abs(mtm - 101_000.0) < 0.01, f"Expected 101000, got {mtm}"
print(f"  PASS — mark_to_market={mtm:,.2f}")


# ── Test 8: unrealized_pnl ────────────────────────────────────────────────────

print()
print("=" * 60)
print("Test 8: unrealized_pnl")
print("=" * 60)
pnl = p5.unrealized_pnl(_MockPriceFeed({"AAPL": 160.0}))
assert abs(pnl["AAPL"] - 1_000.0) < 0.01, f"Expected 1000, got {pnl['AAPL']}"
print(f"  PASS — unrealized_pnl[AAPL]={pnl['AAPL']:,.2f}")


# ── Test 9: snapshot is JSON-serializable ─────────────────────────────────────

print()
print("=" * 60)
print("Test 9: snapshot() is JSON-serializable")
print("=" * 60)
import json
snap = p5.snapshot()
assert "cash" in snap and "positions" in snap and "cost_basis" in snap
json_str = json.dumps(snap)   # must not raise
parsed = json.loads(json_str)
assert parsed["positions"]["AAPL"] == 100
print(f"  PASS — snapshot={snap}")


# ── Test 10: weighted avg cost_basis on two buys ──────────────────────────────

print()
print("=" * 60)
print("Test 10: Weighted average cost basis on two BUY fills")
print("=" * 60)
p6 = Portfolio(STARTING)
p6.apply_fill(_fill("MSFT", "BUY", 100, 400.0, order_id=1))  # 100 @ 400
p6.apply_fill(_fill("MSFT", "BUY", 100, 420.0, order_id=2))  # 100 @ 420 → avg = 410
expected_basis = (100 * 400 + 100 * 420) / 200
assert abs(p6._cost_basis["MSFT"] - expected_basis) < 0.001
print(f"  PASS — avg cost_basis={p6._cost_basis['MSFT']:.2f} (expected {expected_basis:.2f})")


# ── Test 11: thread safety ────────────────────────────────────────────────────

print()
print("=" * 60)
print("Test 11: Thread safety — 10 concurrent BUY fills")
print("=" * 60)
p7 = Portfolio(10_000_000.0)  # enough cash for all fills
errors = []

def do_fill(i):
    try:
        p7.apply_fill(FillRecord(order_id=i, ticker="SPY", side="BUY",
                                  quantity=1, price=500.0))
    except Exception as e:
        errors.append(e)

threads = [threading.Thread(target=do_fill, args=(i,)) for i in range(10)]
for t in threads: t.start()
for t in threads: t.join()

assert not errors, f"Thread errors: {errors}"
assert p7.positions.get("SPY") == 10
print(f"  PASS — 10 concurrent fills, final SPY={p7.positions['SPY']}, errors={errors}")


# ── Test 12: open and partially cover a short ────────────────────────────────

print()
print("=" * 60)
print("Test 12: Short sale and partial cover")
print("=" * 60)
p8 = Portfolio(STARTING, allow_short_selling=True)
p8.apply_fill(_fill("AAPL", "SELL", 100, 100.0))
assert p8.positions["AAPL"] == -100
assert p8.cash == 110_000.0
assert p8.unrealized_pnl(_MockPriceFeed({"AAPL": 90.0}))["AAPL"] == 1_000.0
p8.apply_fill(_fill("AAPL", "BUY", 40, 90.0, order_id=2))
assert p8.positions["AAPL"] == -60
assert p8.realized_pnl() == 400.0
print("  PASS — signed position, cash, unrealized P&L, and cover P&L are correct")


# ── Test 13: covering through zero opens a new long basis ────────────────────

print()
print("=" * 60)
print("Test 13: Cover through zero into a long position")
print("=" * 60)
p8.apply_fill(_fill("AAPL", "BUY", 80, 110.0, order_id=3))
assert p8.positions["AAPL"] == 20
assert p8._cost_basis["AAPL"] == 110.0
assert p8.realized_pnl() == -200.0
print("  PASS — remaining long position receives the crossing fill price as basis")


print()
print("All Portfolio tests passed.")
