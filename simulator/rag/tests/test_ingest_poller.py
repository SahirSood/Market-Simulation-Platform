import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from scripts.ingest_poller import poll_and_ingest_once


class FakeRepository:
    def __init__(self):
        self.created = False

    def create_tables(self):
        self.created = True


class FakeIngestionService:
    ticker_to_cik = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
    }

    def __init__(self):
        self.ingested = []

    def ingest(self, tickers, forms, max_filings_per_ticker):
        self.ingested.append(
            {
                "tickers": tickers,
                "forms": forms,
                "max_filings_per_ticker": max_filings_per_ticker,
            }
        )
        return {"processed": 1, "inserted": 1}


def test_poller_ingests_only_tickers_with_detected_filings(monkeypatch):
    detected = {
        "0000320193": [{"accessionNumber": "0000320193-24-000003"}],
        "0000789019": [],
    }

    def fake_detect(ciks, rag_repository, max_items):
        assert ciks == ["0000320193", "0000789019"]
        assert max_items == 2
        return detected

    monkeypatch.setattr("scripts.ingest_poller.detect_new_filings_for_ciks", fake_detect)

    repo = FakeRepository()
    service = FakeIngestionService()
    result = poll_and_ingest_once(
        tickers=["AAPL", "MSFT", "ZZZ"],
        db_url="sqlite:///:memory:",
        max_filings=2,
        forms=["10-K", "10-Q"],
        repository=repo,
        ingestion_service=service,
    )

    assert repo.created is True
    assert result["tracked_ciks"] == ["0000320193", "0000789019"]
    assert result["unknown_tickers"] == ["ZZZ"]
    assert result["updated_tickers"] == ["AAPL"]
    assert service.ingested == [
        {
            "tickers": ["AAPL"],
            "forms": ("10-K", "10-Q"),
            "max_filings_per_ticker": 2,
        }
    ]


class DynamicCikService:
    ticker_to_cik = {}

    def __init__(self):
        self.ingested = []

    def get_cik_for_ticker(self, ticker):
        return {"PLTR": "0001321655"}.get(str(ticker).upper())

    def ingest(self, tickers, forms, max_filings_per_ticker):
        self.ingested.append(
            {
                "tickers": tickers,
                "forms": forms,
                "max_filings_per_ticker": max_filings_per_ticker,
            }
        )
        return {"processed": 1, "inserted": 1}


def test_poller_uses_dynamic_cik_resolver(monkeypatch):
    def fake_detect(ciks, rag_repository, max_items):
        assert ciks == ["0001321655"]
        return {"0001321655": [{"accessionNumber": "0001321655-24-000001"}]}

    monkeypatch.setattr("scripts.ingest_poller.detect_new_filings_for_ciks", fake_detect)

    repo = FakeRepository()
    service = DynamicCikService()
    result = poll_and_ingest_once(
        tickers=["PLTR"],
        db_url="sqlite:///:memory:",
        max_filings=1,
        forms=["10-K"],
        repository=repo,
        ingestion_service=service,
    )

    assert result["tracked_ciks"] == ["0001321655"]
    assert result["unknown_tickers"] == []
    assert result["updated_tickers"] == ["PLTR"]
    assert service.ingested[0]["tickers"] == ["PLTR"]
