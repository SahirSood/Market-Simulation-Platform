"""
Run from the simulator/ directory:
    python tests/test_base_bot.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import BaseBot, OrderDecision
from config import STARTING_CASH


# ── Helpers ──────────────────────────────────────────────────────────────────

class _MockNewsFeed:
    def get_trending(self):
        return [{"title": "Markets rise", "source": "Reuters", "age_minutes": 10, "age_label": "10 min ago"}]
    def get_recent(self):
        return [{"title": "Fed holds rates", "source": "Bloomberg", "age_minutes": 5, "age_label": "5 min ago"}]

class _MockPriceFeed:
    def get_price(self, ticker): return 150.0

class _DummyBot(BaseBot):
    """Minimal concrete subclass — used to test BaseBot without hitting LLM."""
    def decide(self) -> OrderDecision:
        return OrderDecision(
            action="HOLD", ticker=None, quantity=None,
            limit_price=None, reasoning="test hold", headline_used=None,
        )


# ── Test 1: BaseBot cannot be instantiated directly ───────────────────────────

print("=" * 60)
print("Test 1: BaseBot is abstract — cannot instantiate directly")
print("=" * 60)
try:
    BaseBot("id", "name", "prompt", None, None)
    print("  FAIL — should have raised TypeError")
except TypeError as e:
    print(f"  PASS — TypeError: {e}")


# ── Test 2: DummyBot works and returns HOLD ───────────────────────────────────

print()
print("=" * 60)
print("Test 2: Subclass with dummy decide() returns HOLD")
print("=" * 60)
bot = _DummyBot("dummy-1", "DummyBot", "You are a test bot.",
                _MockPriceFeed(), _MockNewsFeed(), llm_provider="claude")
decision = bot.decide()
assert decision.action == "HOLD"
assert decision.ticker is None
print(f"  PASS — action={decision.action}, ticker={decision.ticker}")


# ── Test 3: get_context() returns correct structure ───────────────────────────

print()
print("=" * 60)
print("Test 3: get_context() structure")
print("=" * 60)
ctx = bot.get_context()
assert "trending_headlines" in ctx
assert "recent_headlines"   in ctx
assert "positions"          in ctx
assert "cash"               in ctx
assert "total_positions"    in ctx
assert ctx["cash"]           == STARTING_CASH
assert ctx["total_positions"] == 0
print(f"  PASS — keys: {list(ctx.keys())}")
print(f"  cash={ctx['cash']}, positions={ctx['total_positions']}")
print(f"  trending headlines: {len(ctx['trending_headlines'])}")
print(f"  recent headlines:   {len(ctx['recent_headlines'])}")


# ── Test 4: _call_llm returns valid JSON with all required fields ──────────────

print()
print("=" * 60)
print("Test 4: _call_llm with real LLM — all required fields present")
print("=" * 60)
prompt = bot._build_prompt(ctx)
result = bot._call_llm(prompt)

required_fields = {"action", "ticker", "quantity", "limit_price", "reasoning", "headline_used"}
missing = required_fields - result.keys()
assert not missing, f"Missing fields: {missing}"
assert result["action"] in ("BUY", "SELL", "HOLD"), f"Invalid action: {result['action']}"

print(f"  PASS — action={result['action']}, ticker={result['ticker']}")
print(f"  reasoning: {result['reasoning']}")
print(f"  headline_used: {result['headline_used']}")


# ── Test 5: _call_llm returns HOLD fallback on invalid provider ───────────────

print()
print("=" * 60)
print("Test 5: Unknown llm_provider raises ValueError at init")
print("=" * 60)
try:
    _DummyBot("x", "x", "x", _MockPriceFeed(), _MockNewsFeed(), llm_provider="grok")
    print("  FAIL — should have raised ValueError")
except ValueError as e:
    print(f"  PASS — ValueError: {e}")
