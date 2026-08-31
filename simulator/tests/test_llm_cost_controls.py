import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base_bot as base_bot_module
from base_bot import BaseBot, OrderDecision
from bots.degen_bot import DegenBot
from config import (
    BENCHMARK_TICKERS,
    LLM_MAX_TOKENS,
    LLM_PROMPT_CACHE_ENABLED,
    PROMPT_EVIDENCE_CHARS,
    PROMPT_EVIDENCE_LIMIT,
    PROMPT_RECENT_LIMIT,
    PROMPT_TICKER_HEADLINE_LIMIT,
    PROMPT_TICKER_LIMIT,
    PROMPT_TRENDING_LIMIT,
    TRADABLE_TICKERS,
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

    def get_tradable_tickers(self):
        return list(TRADABLE_TICKERS)


class FakeClaudeMessages:
    def __init__(self, payload=None):
        self.calls = []
        self.payload = payload or {
            "action": "HOLD",
            "ticker": None,
            "quantity": None,
            "limit_price": None,
            "reasoning": "unchanged context",
            "headline_used": None,
        }

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    text=json.dumps(self.payload)
                )
            ],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=80),
        )


class FakeClaudeClient:
    def __init__(self, payload=None):
        self.messages = FakeClaudeMessages(payload)


class FakeOpenAICompletions:
    def __init__(self, contents):
        self.calls = []
        self.contents = list(contents)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0) if self.contents else ""
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ],
            usage=SimpleNamespace(prompt_tokens=900, completion_tokens=70, total_tokens=970),
        )


class FakeOpenAIClient:
    def __init__(self, contents):
        self.chat = SimpleNamespace(completions=FakeOpenAICompletions(contents))


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


def _openai_bot():
    return DummyBot(
        "dummy-openai",
        "Dummy OpenAI",
        "You are a test bot.",
        PriceFeed(),
        NewsFeed(),
        llm_provider="openai",
    )


def _named_bot(name):
    return DummyBot(
        "dummy",
        name,
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
    assert context["tradable_tickers"] == list(TRADABLE_TICKERS)
    assert context["benchmark_tickers"] == list(BENCHMARK_TICKERS)
    for ticker in [*TRADABLE_TICKERS, *BENCHMARK_TICKERS]:
        assert ticker in context["market_prices"]


def test_context_prioritizes_news_discovered_tickers_for_ticker_headlines():
    class SymbolNewsFeed(NewsFeed):
        def get_recent(self, n=25):
            return [_headline("PLTR jumps after new government contract")]

    bot = DummyBot(
        "dummy",
        "Dummy",
        "You are a test bot.",
        PriceFeed(),
        SymbolNewsFeed(),
        llm_provider="claude",
    )

    context = bot.get_context()

    assert context["research_candidates"] == ["PLTR"]
    assert next(iter(context["ticker_headlines"])) == "PLTR"


def test_retrieve_evidence_triggers_predecision_research_coverage():
    class Repo:
        def __init__(self):
            self.calls = []

        def retrieve_evidence(self, ticker, query_text, top_k, embedding_service=None, as_of_date=None):
            self.calls.append(ticker)
            return []

    class Coordinator:
        def __init__(self):
            self.calls = []

        def ensure_context_coverage(self, context, source_bot=None):
            self.calls.append((context, source_bot))
            return [{"ticker": "PLTR", "status": "ingested"}]

    repo = Repo()
    coordinator = Coordinator()
    bot = _bot()
    bot.rag_repository = repo
    bot.research_coordinator = coordinator

    bot._retrieve_evidence(
        {
            "trending_headlines": [_headline("PLTR revenue rises")],
            "recent_headlines": [],
            "ticker_headlines": {},
            "research_candidates": ["PLTR"],
            "as_of_date": None,
        }
    )

    assert coordinator.calls[0][1] == "dummy"
    assert repo.calls[0] == "PLTR"


def test_prompt_includes_tradable_universe():
    bot = _bot()

    prompt = bot._build_prompt(bot.get_context())

    assert "TRADABLE TICKERS" in prompt
    assert TRADABLE_TICKERS[0] in prompt
    assert "BENCHMARK TICKERS" in prompt
    assert BENCHMARK_TICKERS[0] in prompt


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
    assert first["llm_input_tokens"] == 1000
    assert first["llm_output_tokens"] == 80
    assert first["llm_total_tokens"] == 1080
    assert first["llm_estimated_cost_usd"] > 0
    expected_calls = 1 if LLM_PROMPT_CACHE_ENABLED else 2
    assert len(fake_client.messages.calls) == expected_calls
    if LLM_PROMPT_CACHE_ENABLED:
        assert second["llm_call_made"] is False
        assert second["llm_estimated_cost_usd"] == 0.0


def test_unchanged_prompt_holds_without_second_paid_call(monkeypatch):
    monkeypatch.setattr(base_bot_module, "LLM_PROMPT_CACHE_ENABLED", True)
    monkeypatch.setattr(base_bot_module, "LLM_SKIP_UNCHANGED_PROMPTS", True)
    bot = _bot()
    fake_client = FakeClaudeClient(
        {
            "action": "BUY",
            "ticker": "NVDA",
            "quantity": 5,
            "limit_price": 100.0,
            "reasoning": "first call",
            "headline_used": "headline",
            "evidence_ids": [],
        }
    )
    bot._claude_client = fake_client

    first = bot._call_llm("same prompt")
    second = bot._call_llm("same prompt")

    assert first["action"] == "BUY"
    assert first["llm_call_made"] is True
    assert second["action"] == "HOLD"
    assert second["llm_call_made"] is False
    assert "skipped LLM call" in second["reasoning"]
    assert len(fake_client.messages.calls) == 1


def test_degen_keeps_hold_when_provider_call_fails():
    class FailingMessages:
        def create(self, **kwargs):
            raise RuntimeError("provider unavailable")

    bot = DegenBot(PriceFeed(), NewsFeed(), llm_provider="claude")
    bot._claude_client = SimpleNamespace(messages=FailingMessages())

    decision = bot.decide()

    assert decision.action == "HOLD"
    assert "defaulting to HOLD" in decision.reasoning


def test_provider_failure_reason_includes_public_error_summary():
    class FailingMessages:
        def create(self, **kwargs):
            raise RuntimeError("model not found")

    bot = _bot()
    bot._claude_client = SimpleNamespace(messages=FailingMessages())

    result = bot._call_llm("prompt")

    assert result["action"] == "HOLD"
    assert "RuntimeError: model not found" in result["reasoning"]


def test_llm_ticker_outside_tradable_universe_is_forced_to_hold():
    bot = _bot()
    bot._claude_client = FakeClaudeClient(
        {
            "action": "BUY",
            "ticker": "NOTREAL",
            "quantity": 10,
            "limit_price": 100.0,
            "reasoning": "outside universe",
            "headline_used": "test",
            "evidence_ids": [1],
        }
    )

    result = bot._call_llm("invalid ticker prompt")

    assert result["action"] == "HOLD"
    assert result["ticker"] is None
    assert result["evidence_ids"] == []
    assert result["hold_cause"] == "guardrail"
    assert "outside the tradable universe" in result["reasoning"]


def test_llm_payload_normalizes_public_decision_fields():
    bot = _bot()
    bot._claude_client = FakeClaudeClient(
        {
            "action": "buy",
            "ticker": "nvda",
            "quantity": "12",
            "limit_price": "101.25",
            "reasoning": "Evidence supports a small public trade rationale.",
            "headline_used": 123,
            "confidence": "1.5",
            "evidence_ids": ["7", "bad", 7],
            "research_tickers": ["msft", "not real"],
        }
    )

    result = bot._call_llm("normalization prompt")

    assert result["action"] == "BUY"
    assert result["ticker"] == "NVDA"
    assert result["quantity"] == 12
    assert result["limit_price"] == 101.25
    assert result["confidence"] == 1.0
    assert result["evidence_ids"] == [7]
    assert result["research_tickers"] == ["MSFT"]


def test_openai_empty_visible_content_retries_with_low_reasoning():
    payload = {
        "action": "BUY",
        "ticker": "MSFT",
        "quantity": 4,
        "limit_price": None,
        "reasoning": "Earnings beat supports a small replay buy.",
        "headline_used": "MSFT beats estimates",
        "confidence": 0.7,
        "evidence_ids": [],
    }
    bot = _openai_bot()
    bot._openai_client = FakeOpenAIClient(["", json.dumps(payload)])

    result = bot._call_llm("openai retry prompt")

    calls = bot._openai_client.chat.completions.calls
    assert result["action"] == "BUY"
    assert result["ticker"] == "MSFT"
    assert len(calls) == 2
    assert calls[1]["reasoning_effort"] == "low"
    assert calls[1]["max_completion_tokens"] >= 1200


def test_llm_json_parser_accepts_fences_and_surrounding_text():
    parsed = DummyBot._parse_llm_json(
        'Here is the decision:\n```json\n{"action":"HOLD","reasoning":"wait"}\n```'
    )

    assert parsed == {"action": "HOLD", "reasoning": "wait"}


def test_openai_content_list_is_parsed_as_text():
    payload = {
        "action": "HOLD",
        "reasoning": "No trade",
    }
    bot = _openai_bot()
    bot._openai_client = FakeOpenAIClient([[{"type": "text", "text": json.dumps(payload)}]])

    result = bot._call_llm("openai content list prompt")

    assert result["action"] == "HOLD"
    assert result["reasoning"] == "No trade"
    assert result["llm_input_tokens"] == 900


def test_finalize_decision_forces_hold_for_invalid_trade_shape():
    bot = _bot()

    result = bot._finalize_decision_payload({
        "action": "BUY",
        "ticker": "NVDA",
        "quantity": "lots",
        "limit_price": 100.0,
        "reasoning": "bad quantity",
        "headline_used": None,
    })

    assert result["action"] == "HOLD"
    assert result["ticker"] is None
    assert result["quantity"] is None
    assert result["hold_cause"] == "invalid_output"
    assert "invalid or missing quantity" in result["reasoning"]


def test_evidence_required_bot_holds_when_evidence_store_is_unavailable():
    bot = _named_bot("AnalystBot")
    raw = {
        "action": "BUY",
        "ticker": "NVDA",
        "quantity": 10,
        "limit_price": 100.0,
        "reasoning": "trade without citations",
        "headline_used": "headline",
        "confidence": 0.7,
        "evidence_ids": [],
    }

    result = bot._apply_evidence_guardrail(raw)

    assert result["action"] == "HOLD"
    assert result["hold_cause"] == "weak_evidence"
    assert "evidence store unavailable" in result["reasoning"]


def test_degen_does_not_trade_when_llm_call_falls_back_to_hold():
    bot = DegenBot(PriceFeed(), NewsFeed(), llm_provider="claude")
    bot._claude_client = None

    decision = bot.decide()

    assert decision.action == "HOLD"
    assert decision.quantity is None
    assert decision.llm_call_made is False
