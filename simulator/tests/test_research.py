import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research import ResearchCoordinator, extract_candidate_tickers


def test_extract_candidate_tickers_uses_company_aliases_and_cashtags():
    text = "Netflix rallies while Bank of America upgrades $AMD before earnings"

    assert set(extract_candidate_tickers(text)) == {"NFLX", "BAC", "AMD"}


def test_extract_candidate_tickers_ignores_common_uppercase_words():
    text = "SEC says AI ETF flows rise while Apple shares fall"

    assert extract_candidate_tickers(text) == ["AAPL"]


def test_extract_candidate_tickers_accepts_news_symbols_without_seed():
    text = "PLTR jumps after new contract while SEC reviews AI ETF disclosures"

    assert extract_candidate_tickers(text) == ["PLTR"]


def test_extract_candidate_tickers_rejects_publication_and_metric_fragments():
    text = "WSJ: Company targets K3 milestone while PLTR shares rally"

    assert extract_candidate_tickers(text) == ["PLTR"]


class FakeRepository:
    def __init__(self, covered=None):
        self.covered = {str(t).upper() for t in (covered or [])}

    def count_documents_by_ticker(self, ticker):
        return 1 if str(ticker).upper() in self.covered else 0


class FakePriceFeed:
    def __init__(self):
        self.added = []

    def get_price(self, ticker):
        return 25.0

    def add_tradable_ticker(self, ticker):
        self.added.append(str(ticker).upper())
        return True


def test_research_coordinator_ingests_missing_news_ticker_before_decision(monkeypatch):
    repo = FakeRepository()
    price_feed = FakePriceFeed()
    calls = []

    def fake_poll(**kwargs):
        calls.append(kwargs)
        return {"updated_tickers": ["PLTR"], "unknown_tickers": []}

    def fake_embed(**kwargs):
        return {"embedded": 3}

    monkeypatch.setattr("research.poll_and_ingest_once", fake_poll)
    monkeypatch.setattr("research.embed_once", fake_embed)

    coordinator = ResearchCoordinator(
        repository=repo,
        db_url="sqlite:///:memory:",
        price_feed=price_feed,
        engine_adapter=None,
        cooldown_mins=0,
        max_tickers_per_context=2,
        expand_tradable_universe=True,
    )

    events = coordinator.ensure_context_coverage(
        {
            "research_candidates": ["PLTR"],
            "ticker_headlines": {},
            "trending_headlines": [],
            "recent_headlines": [],
            "tradable_tickers": [],
        },
        source_bot="bot-1",
    )

    assert events[0]["status"] == "ingested"
    assert calls[0]["tickers"] == ["PLTR"]
    assert price_feed.added == ["PLTR"]


def test_research_coordinator_skips_ingestion_for_existing_rag_ticker(monkeypatch):
    repo = FakeRepository({"PLTR"})
    price_feed = FakePriceFeed()

    def fail_poll(**kwargs):
        raise AssertionError("poller should not run for covered ticker")

    monkeypatch.setattr("research.poll_and_ingest_once", fail_poll)

    coordinator = ResearchCoordinator(
        repository=repo,
        db_url="sqlite:///:memory:",
        price_feed=price_feed,
        engine_adapter=None,
        cooldown_mins=0,
        expand_tradable_universe=True,
    )

    event = coordinator.ensure_ticker("PLTR", source_bot="bot-1")

    assert event["status"] == "already_covered"
    assert price_feed.added == ["PLTR"]


def test_research_coordinator_does_not_expand_trading_universe_by_default(monkeypatch):
    repo = FakeRepository({"PLTR"})
    price_feed = FakePriceFeed()

    coordinator = ResearchCoordinator(
        repository=repo,
        db_url="sqlite:///:memory:",
        price_feed=price_feed,
        engine_adapter=None,
        cooldown_mins=0,
    )

    event = coordinator.ensure_ticker("PLTR", source_bot="bot-1")

    assert event["status"] == "already_covered"
    assert price_feed.added == []
