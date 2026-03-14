"""
Run from the simulator/ directory:
    python tests/test_bots.py
"""
import sys
import os
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.bear_bot      import BearBot
from bots.degen_bot     import DegenBot
from bots.analyst_bot   import AnalystBot
from bots.contrarian_bot import ContrarianBot
from bots.macro_bot     import MacroBot
from base_bot           import OrderDecision


# ── Shared mocks ─────────────────────────────────────────────────────────────

class _MockNewsFeed:
    def get_trending(self):
        return [
            {"title": "Fed signals rate cut in March", "source": "WSJ",
             "age_minutes": 5, "age_label": "5 min ago"},
            {"title": "NVDA smashes earnings estimates", "source": "CNBC",
             "age_minutes": 20, "age_label": "20 min ago"},
        ]
    def get_recent(self):
        return [
            {"title": "Treasury yields surge to 5.2%", "source": "Bloomberg",
             "age_minutes": 2, "age_label": "2 min ago"},
            {"title": "Apple new iPhone launch next week", "source": "Verge",
             "age_minutes": 8, "age_label": "8 min ago"},
        ]

class _MockPriceFeed:
    def get_price(self, ticker): return 489.20
    def get_ohlcv(self, ticker):
        # NVDA opened at 480, currently 489.20 → +1.9% intraday
        return {"open": 480.0, "high": 492.0, "low": 479.0, "close": 480.0, "volume": 5_000_000}


def _llm_sell(prompt):
    return {"action": "SELL", "ticker": "NVDA", "quantity": 100, "limit_price": 485.0,
            "reasoning": "Market is overvalued", "headline_used": "NVDA smashes earnings"}

def _llm_buy(prompt):
    return {"action": "BUY", "ticker": "SPY", "quantity": 50, "limit_price": 490.0,
            "reasoning": "Fed cut is bullish", "headline_used": "Fed signals rate cut"}

def _llm_hold(prompt):
    return {"action": "HOLD", "ticker": None, "quantity": None, "limit_price": None,
            "reasoning": "Uncertain conditions", "headline_used": None}


# ═══════════════════════════════════════════════════════════════════════════════
# DegenBot tests
# ═══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("DegenBot: always uses market orders (limit_price=None)")
print("=" * 60)
degen = DegenBot(_MockPriceFeed(), _MockNewsFeed())
with patch.object(degen, "_call_llm", return_value={
    "action": "BUY", "ticker": "NVDA", "quantity": 150, "limit_price": 490.0,
    "reasoning": "Up only", "headline_used": "NVDA smashes earnings",
}):
    d = degen.decide()
assert d.limit_price is None, f"Expected None, got {d.limit_price}"
assert d.action == "BUY"
print(f"  PASS — limit_price={d.limit_price}, action={d.action}")

print()
print("DegenBot: HOLD → flipped to BUY or SELL (never stays HOLD)")
print("=" * 60)
with patch.object(degen, "_call_llm", return_value=_llm_hold("")):
    d = degen.decide()
assert d.action in ("BUY", "SELL"), f"Expected BUY or SELL, got {d.action}"
print(f"  PASS — HOLD flipped to {d.action}")

print()
print("DegenBot: quantity clamped to 50–200")
print("=" * 60)
with patch.object(degen, "_call_llm", return_value={
    "action": "BUY", "ticker": "NVDA", "quantity": 500, "limit_price": None,
    "reasoning": "All in", "headline_used": None,
}):
    d = degen.decide()
assert d.quantity == 200, f"Expected 200, got {d.quantity}"
with patch.object(degen, "_call_llm", return_value={
    "action": "SELL", "ticker": "NVDA", "quantity": 5, "limit_price": None,
    "reasoning": "Small sell", "headline_used": None,
}):
    d = degen.decide()
assert d.quantity == 50, f"Expected 50, got {d.quantity}"
print(f"  PASS — quantity clamped correctly")


# ═══════════════════════════════════════════════════════════════════════════════
# AnalystBot tests
# ═══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 60)
print("AnalystBot: cooldown prevents trade within 1 hour")
print("=" * 60)
analyst = AnalystBot(_MockPriceFeed(), _MockNewsFeed())
analyst._last_trade_time = time.time()  # just traded

call_count = [0]
original_call_llm = analyst._call_llm
def counting_llm(prompt):
    call_count[0] += 1
    return original_call_llm(prompt)

with patch.object(analyst, "_call_llm", side_effect=counting_llm):
    d = analyst.decide()
assert d.action == "HOLD", f"Expected HOLD during cooldown, got {d.action}"
assert call_count[0] == 0, f"Expected 0 LLM calls, got {call_count[0]}"
print(f"  PASS — HOLD without LLM call during cooldown")

print()
print("AnalystBot: derives limit_price when LLM omits it")
print("=" * 60)
analyst2 = AnalystBot(_MockPriceFeed(), _MockNewsFeed())
with patch.object(analyst2, "_call_llm", return_value={
    "action": "BUY", "ticker": "AAPL", "quantity": 20, "limit_price": None,
    "reasoning": "Strong conviction on AAPL", "headline_used": "Apple new iPhone",
}):
    d = analyst2.decide()
assert d.limit_price is not None, "Expected limit_price to be derived"
expected = round(489.20 * 0.995, 2)
assert d.limit_price == expected, f"Expected {expected}, got {d.limit_price}"
print(f"  PASS — limit_price derived as {d.limit_price} (0.5% below mid)")

print()
print("AnalystBot: quantity clamped to 10–50")
print("=" * 60)
analyst3 = AnalystBot(_MockPriceFeed(), _MockNewsFeed())
with patch.object(analyst3, "_call_llm", return_value={
    "action": "BUY", "ticker": "AAPL", "quantity": 200, "limit_price": 485.0,
    "reasoning": "Strong", "headline_used": None,
}):
    d = analyst3.decide()
assert d.quantity == 50, f"Expected 50, got {d.quantity}"
print(f"  PASS — quantity clamped to 50")


# ═══════════════════════════════════════════════════════════════════════════════
# ContrarianBot tests
# ═══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 60)
print("ContrarianBot: intraday move injected into prompt")
print("=" * 60)
contrarian = ContrarianBot(_MockPriceFeed(), _MockNewsFeed())
captured_prompts = []
with patch.object(contrarian, "_call_llm", side_effect=lambda p: (captured_prompts.append(p), _llm_sell(p))[1]):
    contrarian.decide()
assert len(captured_prompts) == 1
# NVDA is up ~1.9% → should appear in prompt
assert "NVDA" in captured_prompts[0] and ("up" in captured_prompts[0] or "INTRADAY" in captured_prompts[0])
print(f"  PASS — intraday move context injected")
print(f"  prompt prefix: {captured_prompts[0][:120]}...")

print()
print("ContrarianBot: quantity clamped to 25–100")
print("=" * 60)
with patch.object(contrarian, "_call_llm", return_value={
    "action": "BUY", "ticker": "NVDA", "quantity": 500, "limit_price": 485.0,
    "reasoning": "Fade the move", "headline_used": None,
}):
    d = contrarian.decide()
assert d.quantity == 100, f"Expected 100, got {d.quantity}"
print(f"  PASS — quantity clamped to 100")


# ═══════════════════════════════════════════════════════════════════════════════
# MacroBot tests
# ═══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 60)
print("MacroBot: HOLD without LLM call when no macro headlines")
print("=" * 60)

class _NoMacroNewsFeed:
    def get_trending(self):
        return [{"title": "Apple releases new iPhone 17", "source": "Verge",
                 "age_minutes": 10, "age_label": "10 min ago"}]
    def get_recent(self):
        return [{"title": "NVDA CEO joins gaming conference", "source": "IGN",
                 "age_minutes": 5, "age_label": "5 min ago"}]

macro = MacroBot(_MockPriceFeed(), _NoMacroNewsFeed())
call_count2 = [0]
with patch.object(macro, "_call_llm", side_effect=lambda p: (call_count2.__setitem__(0, call_count2[0]+1), _llm_buy(p))[1]):
    d = macro.decide()
assert d.action == "HOLD"
assert call_count2[0] == 0
print(f"  PASS — HOLD without LLM call (no macro headlines)")

print()
print("MacroBot: trades when macro headlines present")
print("=" * 60)
macro2 = MacroBot(_MockPriceFeed(), _MockNewsFeed())
with patch.object(macro2, "_call_llm", return_value={
    "action": "BUY", "ticker": "TLT", "quantity": 30, "limit_price": 95.0,
    "reasoning": "Fed cut bullish for bonds", "headline_used": "Fed signals rate cut",
}):
    d = macro2.decide()
assert d.action == "BUY"
assert d.ticker == "TLT"
print(f"  PASS — {d.action} {d.quantity} {d.ticker}")

print()
print("MacroBot: rejects non-ETF ticker → HOLD")
print("=" * 60)
macro3 = MacroBot(_MockPriceFeed(), _MockNewsFeed())
with patch.object(macro3, "_call_llm", return_value={
    "action": "BUY", "ticker": "AAPL", "quantity": 50, "limit_price": 185.0,
    "reasoning": "Apple will benefit from rate cut", "headline_used": "Fed signals rate cut",
}):
    d = macro3.decide()
assert d.action == "HOLD", f"Expected HOLD, got {d.action}"
assert d.ticker is None
print(f"  PASS — AAPL rejected, returned HOLD")


# ═══════════════════════════════════════════════════════════════════════════════
# All 5 bots: same macro headline → different decisions
# ═══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 60)
print("All 5 bots: same headline → meaningfully different decisions")
print("=" * 60)

class _FedNewsFeed:
    def get_trending(self):
        return [{"title": "Fed cuts rates by 50bps — markets surge", "source": "Reuters",
                 "age_minutes": 3, "age_label": "3 min ago"}]
    def get_recent(self):
        return self.get_trending()

feed = _FedNewsFeed()
pf   = _MockPriceFeed()

bear_bot  = BearBot(pf, feed)
degen_bot = DegenBot(pf, feed)
analy_bot = AnalystBot(pf, feed)
contr_bot = ContrarianBot(pf, feed)
macro_bot = MacroBot(pf, feed)

responses = {
    "BearBot":      {"action": "SELL", "ticker": "SPY",  "quantity": 100, "limit_price": 488.0, "reasoning": "Rate cut = desperation", "headline_used": "Fed cuts"},
    "DegenBot":     {"action": "BUY",  "ticker": "SPY",  "quantity": 200, "limit_price": None,  "reasoning": "To the moon", "headline_used": "Fed cuts"},
    "AnalystBot":   {"action": "BUY",  "ticker": "TLT",  "quantity": 30,  "limit_price": 94.5,  "reasoning": "Bonds benefit", "headline_used": "Fed cuts"},
    "ContrarianBot":{"action": "SELL", "ticker": "SPY",  "quantity": 75,  "limit_price": 490.0, "reasoning": "Fade the surge", "headline_used": "Fed cuts"},
    "MacroBot":     {"action": "BUY",  "ticker": "TLT",  "quantity": 50,  "limit_price": 96.0,  "reasoning": "Rate cut bullish bonds", "headline_used": "Fed cuts"},
}

all_bots = [bear_bot, degen_bot, analy_bot, contr_bot, macro_bot]
decisions = {}
for bot in all_bots:
    with patch.object(bot, "_call_llm", return_value=responses[bot.name]):
        decisions[bot.name] = bot.decide()

for name, d in decisions.items():
    print(f"  {name:15s} → {d.action:4s} {str(d.quantity):5s} {str(d.ticker):6s} @ {d.limit_price}")

# Sanity checks
assert decisions["BearBot"].action    != "BUY"
assert decisions["DegenBot"].limit_price is None        # always market orders
assert decisions["AnalystBot"].limit_price is not None  # always limit orders
assert decisions["MacroBot"].ticker   in ({"SPY", "QQQ", "TLT", "GLD", "IEF"} | {None})
print("  PASS — all personality constraints respected")


print()
print("All bot tests passed.")
