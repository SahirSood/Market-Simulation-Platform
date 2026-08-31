import os
import sys
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.bear_bot import BearBot
from bots.macro_bot import MacroBot


class PriceFeed:
    def get_price(self, ticker):
        return 100.0

    def get_ohlcv(self, ticker):
        return {"open": 98.0, "high": 101.0, "low": 97.0, "close": 99.0, "volume": 1_000_000}

    def get_tradable_tickers(self):
        return ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY", "QQQ"]


class NewsFeed:
    def __init__(self, trending=None, recent=None):
        self._trending = trending or []
        self._recent = recent or []

    def get_trending(self, n=25):
        return self._trending[:n]

    def get_recent(self, n=25):
        return self._recent[:n]


class EvidenceRepo:
    def retrieve_evidence(self, ticker, query_text, top_k, embedding_service=None, as_of_date=None):
        return [
            {
                "chunk_id": 1,
                "document_id": 1,
                "ticker": ticker or "SPY",
                "source_url": "https://example.com/evidence",
                "form_type": "10-Q",
                "accession_no": "0000000000-26-000001",
                "published_at": datetime(2026, 1, 1),
                "content": "evidence for the selected market signal",
                "score": 0.5,
            }
        ][:top_k]


def _headline(title):
    return {
        "title": title,
        "source": "Test",
        "age_minutes": 1,
        "age_label": "1 min ago",
    }


def test_bear_bot_forces_market_sell_for_sell_signals():
    bot = BearBot(
        PriceFeed(),
        NewsFeed(trending=[_headline("NVDA rally looks stretched")]),
    )

    with patch.object(bot, "_call_llm", return_value={
        "action": "SELL",
        "ticker": "NVDA",
        "quantity": 75,
        "limit_price": 99.0,
        "reasoning": "The rally is fragile.",
        "headline_used": "NVDA rally looks stretched",
    }):
        decision = bot.decide()

    assert decision.action == "SELL"
    assert decision.ticker == "NVDA"
    assert decision.quantity == 75
    assert decision.limit_price is None


def test_bear_bot_never_allows_buy():
    bot = BearBot(
        PriceFeed(),
        NewsFeed(trending=[_headline("NVDA reports strong demand")]),
    )

    with patch.object(bot, "_call_llm", return_value={
        "action": "BUY",
        "ticker": "NVDA",
        "quantity": 75,
        "limit_price": 101.0,
        "reasoning": "Positive demand signal.",
        "headline_used": "NVDA reports strong demand",
    }):
        decision = bot.decide()

    assert decision.action == "HOLD"
    assert decision.ticker is None
    assert decision.quantity is None


def test_macro_bot_broader_macro_language_reaches_llm():
    bot = MacroBot(
        PriceFeed(),
        NewsFeed(
            trending=[_headline("Jobless claims rise while PMI slips")],
            recent=[_headline("Credit spreads widen as liquidity tightens")],
        ),
        rag_repository=EvidenceRepo(),
    )
    calls = []

    with patch.object(bot, "_call_llm", side_effect=lambda prompt: calls.append(prompt) or {
        "action": "HOLD",
        "ticker": None,
        "quantity": None,
        "limit_price": None,
        "reasoning": "Macro evidence is mixed.",
        "headline_used": None,
    }):
        decision = bot.decide()

    assert decision.action == "HOLD"
    assert len(calls) == 1
    assert "Jobless claims" in calls[0]
    assert "Credit spreads" in calls[0]


def test_macro_bot_blocks_company_ticker_even_on_macro_signal():
    bot = MacroBot(
        PriceFeed(),
        NewsFeed(trending=[_headline("Fed cuts rates by 50bps")]),
    )

    with patch.object(bot, "_call_llm", return_value={
        "action": "BUY",
        "ticker": "AAPL",
        "quantity": 50,
        "limit_price": 100.0,
        "reasoning": "Lower rates may help growth equities.",
        "headline_used": "Fed cuts rates by 50bps",
    }):
        decision = bot.decide()

    assert decision.action == "HOLD"
    assert decision.ticker is None
    assert decision.hold_cause == "guardrail"


def test_macro_bot_can_trade_focused_ticker_on_macro_signal():
    bot = MacroBot(
        PriceFeed(),
        NewsFeed(trending=[_headline("Fed cuts rates by 50bps")]),
    )

    with patch.object(bot, "_call_llm", return_value={
        "action": "BUY",
        "ticker": "NVDA",
        "quantity": 50,
        "limit_price": 100.0,
        "reasoning": "Lower rates may support growth equities.",
        "headline_used": "Fed cuts rates by 50bps",
    }):
        decision = bot.decide()

    assert decision.action == "BUY"
    assert decision.ticker == "NVDA"
