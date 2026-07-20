import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import BaseBot, OrderDecision
from config import (
    LLM_MAX_TOKENS,
    LLM_PROMPT_CACHE_ENABLED,
    PROMPT_EVIDENCE_CHARS,
    PROMPT_EVIDENCE_LIMIT,
    PROMPT_RECENT_LIMIT,
    PROMPT_TICKER_HEADLINE_LIMIT,
    PROMPT_TICKER_LIMIT,
    PROMPT_TRENDING_LIMIT,
)


class DummyBot(BaseBot):
    def decide(self) -> OrderDecision:
        return OrderDecision(
            action="HOLD",
            ticker=None,
            quantity=None,
            limit_price=None,
            reasoning="test",
            headline_used=None,
        )


class NewsFeed:
    def __init__(self):
        self.calls = {}

    def get_trending(self, n=25):
        self.calls["trending_n"] = n
        return [_headline(f"Trending {i}") for i in range(20)]

    def get_recent(self, n=25):
        self.calls["recent_n"] = n
        return [_headline(f"Recent {i}") for i in range(20)]

    def get_latest(self, ticker, n=5):
        self.calls[f"{ticker}_n"] = n
        return [_headline(f"{ticker} {i}") for i in range(10)]


class PriceFeed:
    def get_price(self, ticker):
        return 100.0

    def get_active_tickers(self):
        return ["AAPL", "MSFT", "NVDA"]


class FakeClaudeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    text=json.dumps(
                        {
                            "action": "HOLD",
                            "ticker": None,
                            "quantity": None,
                            "limit_price": None,
                            "reasoning": "unchanged context",
                            "headline_used": None,
                        }
                    )
                )
            ]
        )


class FakeClaudeClient:
    def __init__(self):
        self.messages = FakeClaudeMessages()


def _headline(title):
    return {
        "title": title,
        "source": "Test",
        "age_label": "now",
    }


def _bot():
    return DummyBot(
        "dummy",
        "Dummy",
        "You are a test bot.",
        PriceFeed(),
        NewsFeed(),
        llm_provider="claude",
    )


def test_context_uses_prompt_headline_limits():
    bot = _bot()

    context = bot.get_context()

    assert len(context["trending_headlines"]) <= PROMPT_TRENDING_LIMIT
    assert len(context["recent_headlines"]) <= PROMPT_RECENT_LIMIT
    assert len(context["ticker_headlines"]) <= PROMPT_TICKER_LIMIT
    if PROMPT_TICKER_LIMIT > 0:
        first_ticker = next(iter(context["ticker_headlines"]))
        assert len(context["ticker_headlines"][first_ticker]) <= PROMPT_TICKER_HEADLINE_LIMIT


def test_evidence_prompt_is_compact_and_does_not_include_long_source_urls():
    bot = _bot()
    evidence_rows = [
        {
            "chunk_id": i + 1,
            "score": 0.2,
            "ticker": "AAPL",
            "form_type": "10-Q",
            "accession_no": f"0000320193-26-00000{i}",
            "source_url": "https://example.com/really/long/source/url/that/should/not/be/in/prompt",
            "content": "x" * (PROMPT_EVIDENCE_CHARS + 25),
        }
        for i in range(max(PROMPT_EVIDENCE_LIMIT + 1, 2))
    ]

    formatted = bot._format_evidence_for_prompt(evidence_rows)

    assert formatted.count("chunk_id=") == PROMPT_EVIDENCE_LIMIT
    assert "really/long/source/url" not in formatted
    assert "..." in formatted


def test_llm_call_uses_max_tokens_and_reuses_identical_prompt():
    bot = _bot()
    fake_client = FakeClaudeClient()
    bot._claude_client = fake_client

    first = bot._call_llm("same prompt")
    second = bot._call_llm("same prompt")

    assert first["action"] == "HOLD"
    assert second["action"] == "HOLD"
    assert fake_client.messages.calls[0]["max_tokens"] == LLM_MAX_TOKENS
    expected_calls = 1 if LLM_PROMPT_CACHE_ENABLED else 2
    assert len(fake_client.messages.calls) == expected_calls
