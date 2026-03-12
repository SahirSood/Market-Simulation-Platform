"""
Run from the simulator/ directory:
    python tests/test_news_feed.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from news_feed import NewsFeed
from config import NEWS_API_KEY

feed = NewsFeed(api_key=NEWS_API_KEY)

print("=" * 70)
print("Test 1: Trending headlines (popularity-ranked)")
print("=" * 70)
trending = feed.get_trending()
for i, h in enumerate(trending, 1):
    print(f"  {i:2d}. [{h['source']}] [{h['age_label']}] {h['title']}")
print(f"\n  Total trending: {len(trending)}")

print()
print("=" * 70)
print("Test 2: Recent headlines (newest first)")
print("=" * 70)
recent = feed.get_recent()
for i, h in enumerate(recent, 1):
    print(f"  {i:2d}. [{h['source']}] [{h['age_label']}] {h['title']}")
print(f"\n  Total recent: {len(recent)}")

print()
print("=" * 70)
print("Test 3: age_minutes field is present and sorted (recent feed)")
print("=" * 70)
ages = [h["age_minutes"] for h in recent]
assert ages == sorted(ages), f"Recent feed not sorted by age: {ages[:5]}"
print(f"  PASS — sorted by age, youngest={ages[0]}min, oldest={ages[-1]}min")

print()
print("=" * 70)
print("Test 4: Cache timing — both feeds second call should be instant")
print("=" * 70)
for name, method in [("get_trending", feed.get_trending), ("get_recent", feed.get_recent)]:
    t0 = time.time()
    method()
    ms = (time.time() - t0) * 1000
    print(f"  {name} cache hit: {ms:.2f}ms")

print()
print("=" * 70)
print("Test 5: Total headline count")
print("=" * 70)
count = feed.get_headline_count()
print(f"  Total cached headlines: {count}")
assert count > 0
print("  PASS")
