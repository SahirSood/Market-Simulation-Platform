"""
Run from the simulator/ directory:
    python tests/test_price_feed.py
"""
import sys
import os
import time

# Allow imports from simulator/ when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from price_feed import PriceFeed

feed = PriceFeed()

print("=" * 50)
print("Test 1: Fetch prices for AAPL, NVDA, RDDT, ARM")
print("=" * 50)
for ticker in ["AAPL", "NVDA", "RDDT", "ARM"]:
    price = feed.get_price(ticker)
    print(f"  {ticker:6s}  ${price:>10.2f}")

print()
print("=" * 50)
print("Test 2: Cache timing — fetch AAPL twice")
print("=" * 50)

# Force stale on AAPL to get a clean first-fetch time
feed._cache.pop("AAPL", None)
t0 = time.time()
feed.get_price("AAPL")
first_ms = (time.time() - t0) * 1000

t0 = time.time()
feed.get_price("AAPL")
second_ms = (time.time() - t0) * 1000

print(f"  First fetch:  {first_ms:.1f}ms")
print(f"  Cache hit:    {second_ms:.2f}ms")
print(f"  Speedup:      {first_ms / max(second_ms, 0.01):.0f}x faster")

print()
print("=" * 50)
print("Test 3: Active tickers")
print("=" * 50)
active = feed.get_active_tickers()
print(f"  Active tickers: {active}")
assert set(active) == {"AAPL", "NVDA", "RDDT", "ARM"}, f"Expected 4 tickers, got: {active}"
print("  PASS — all 4 tickers tracked")
