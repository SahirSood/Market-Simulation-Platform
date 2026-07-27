import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from base_bot import BaseBot, OrderDecision
from rag.repository import RagRepository
from reasoning_log import ReasoningLog


class MockNewsFeed:
    def get_trending(self):
        return [{"title": "Inflation cools as CPI slows", "source": "Reuters", "age_label": "5 min ago"}]

    def get_recent(self):
        return [{"title": "Bond yields decline after CPI", "source": "Bloomberg", "age_label": "2 min ago"}]

    def get_latest(self, ticker: str, n: int = 3):
        if ticker == "TLT":
            return [{"title": "Treasury ETF rises on lower yields", "source": "CNBC", "age_label": "1 min ago"}]
        return []


class MockPriceFeed:
    def get_price(self, ticker):
        return 100.0

    def get_active_tickers(self):
        return ["TLT"]


class DummyRagBot(BaseBot):
    def decide(self) -> OrderDecision:
        context = self.get_context()
        prompt = self._build_prompt(context)
        raw = self._call_llm(prompt)
        raw = self._apply_evidence_guardrail(raw)
        return OrderDecision(**raw)


def _build_repo_with_evidence() -> RagRepository:
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    repo.add_document_with_chunks(
        ticker="TLT",
        title="Macro filing",
        source_url="http://example.com/evidence",
        content="Inflation is cooling and yields are declining, which supports bonds.",
        chunks=[
            {
                "content": "Inflation is cooling and yields are declining, which supports bonds.",
                "start_pos": 0,
                "end_pos": 72,
                "embedding": None,
            }
        ],
        source_type="sec_filing",
        form_type="8-K",
    )
    return repo


def test_prompt_includes_retrieved_evidence():
    repo = _build_repo_with_evidence()
    bot = DummyRagBot(
        bot_id="dummy-rag-1",
        name="DummyRagBot",
        personality_prompt="You are a test bot.",
        price_feed=MockPriceFeed(),
        news_feed=MockNewsFeed(),
        llm_provider="claude",
        rag_repository=repo,
    )
    bot.base_name = "AnalystBot"

    prompt = bot._build_prompt(bot.get_context())
    assert "RETRIEVED EVIDENCE" in prompt
    assert "chunk_id=" in prompt
    assert "supports bonds" in prompt


def test_weak_evidence_guardrail_forces_hold(monkeypatch):
    # Empty repo => no retrieved evidence rows
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    bot = DummyRagBot(
        bot_id="dummy-rag-2",
        name="DummyRagBot",
        personality_prompt="You are a test bot.",
        price_feed=MockPriceFeed(),
        news_feed=MockNewsFeed(),
        llm_provider="claude",
        rag_repository=repo,
    )
    bot.base_name = "AnalystBot"

    monkeypatch.setattr(
        bot,
        "_call_llm",
        lambda _: {
            "action": "BUY",
            "ticker": "TLT",
            "quantity": 20,
            "limit_price": 99.5,
            "reasoning": "Lower inflation supports bonds",
            "headline_used": "Inflation cools as CPI slows",
            "confidence": 0.72,
            "evidence_ids": [],
            "speculative": False,
        },
    )

    decision = bot.decide()
    assert decision.action == "HOLD"
    assert decision.speculative is False
    assert "Guardrail" in decision.reasoning


def test_speculative_trade_blocked_for_non_speculative_personality(monkeypatch):
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    bot = DummyRagBot(
        bot_id="dummy-rag-3",
        name="DummyRagBot",
        personality_prompt="You are a test bot.",
        price_feed=MockPriceFeed(),
        news_feed=MockNewsFeed(),
        llm_provider="claude",
        rag_repository=repo,
    )
    bot.base_name = "AnalystBot"

    monkeypatch.setattr(
        bot,
        "_call_llm",
        lambda _: {
            "action": "BUY",
            "ticker": "TLT",
            "quantity": 10,
            "limit_price": 99.9,
            "reasoning": "Headline-only momentum trade",
            "headline_used": "Bond yields decline after CPI",
            "confidence": 0.4,
            "evidence_ids": [],
            "speculative": True,
        },
    )

    decision = bot.decide()
    assert decision.action == "HOLD"
    assert decision.speculative is True
    assert "no strong retrieved evidence" in decision.reasoning


def test_reasoning_log_persists_evidence_fields():
    repo = _build_repo_with_evidence()
    bot = DummyRagBot(
        bot_id="dummy-rag-4",
        name="DummyRagBot",
        personality_prompt="You are a test bot.",
        price_feed=MockPriceFeed(),
        news_feed=MockNewsFeed(),
        llm_provider="claude",
        rag_repository=repo,
    )

    decision = OrderDecision(
        action="BUY",
        ticker="TLT",
        quantity=10,
        limit_price=99.8,
        reasoning="Evidence-backed bond buy",
        headline_used="Inflation cools as CPI slows",
        confidence=0.83,
        evidence_ids=[1],
        evidence_urls=["http://example.com/evidence"],
        speculative=False,
    )

    log = ReasoningLog(database_url="sqlite:///:memory:")
    log.log(bot, decision, fills=[])
    rows = log.get_decisions(bot_id="dummy-rag-4", limit=1)
    assert len(rows) == 1
    row = rows[0]
    assert row["confidence"] == 0.83
    assert row["evidence_ids"] == [1]
    assert row["evidence_urls"] == ["http://example.com/evidence"]
    assert row["speculative"] is False
