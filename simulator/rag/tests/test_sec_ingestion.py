import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from simulator.rag.repository import RagRepository
from simulator.rag.sec_ingestion import FetchConfig, SecEdgarIngestionService


class MockResponse:
    def __init__(self, json_data=None, text_data="", status_code=200, headers=None):
        self._json_data = json_data
        self.text = text_data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class MockSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=30):
        self.calls.append(url)
        if "submissions/CIK0000320193.json" in url:
            return MockResponse(
                json_data={
                    "filings": {
                        "recent": {
                            "form": ["10-K", "8-K", "S-8"],
                            "accessionNumber": [
                                "0000320193-24-000001",
                                "0000320193-24-000002",
                                "0000320193-24-000003",
                            ],
                            "primaryDocument": ["d10k.htm", "d8k.htm", "s8.htm"],
                            "filingDate": ["2024-10-25", "2024-11-01", "2024-11-02"],
                        }
                    }
                }
            )

        if url.endswith("/d10k.htm"):
            return MockResponse(text_data="<html><body>Annual report revenue increased strongly.</body></html>")
        if url.endswith("/d8k.htm"):
            return MockResponse(text_data="<html><body>Current report disclosed material event.</body></html>")

        return MockResponse(status_code=404)


def test_chunk_text_validation_and_output():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    svc = SecEdgarIngestionService(repo, session=MockSession(), chunk_size=20, chunk_overlap=5)

    chunks = svc.chunk_text("abcdefghijklmnopqrstuvwxyz")
    assert len(chunks) >= 2
    assert all("content" in c for c in chunks)


def test_sec_ingestion_and_idempotency():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    session = MockSession()
    svc = SecEdgarIngestionService(repository=repo, session=session)

    result_1 = svc.ingest(["AAPL"], forms=("10-K", "10-Q", "8-K"), max_filings_per_ticker=3)
    assert result_1["processed"] == 2
    assert result_1["inserted"] == 2
    assert result_1["skipped_duplicate"] == 0
    assert result_1["failed_fetch"] == 0
    assert repo.count_documents() == 2
    assert repo.count_chunks() >= 2
    stored = repo.get_document_by_accession("0000320193-24-000001")
    assert stored.raw_content == "<html><body>Annual report revenue increased strongly.</body></html>"

    # Repeat run should not duplicate due to content hash deduplication
    result_2 = svc.ingest(["AAPL"], forms=("10-K", "10-Q", "8-K"), max_filings_per_ticker=3)
    assert result_2["processed"] == 2
    assert result_2["inserted"] == 0
    assert result_2["skipped_duplicate"] == 2
    assert repo.count_documents() == 2

    chunks = repo.get_chunks_by_ticker("AAPL", limit=10)
    assert len(chunks) > 0


def test_sec_ingestion_retries_rate_limited_requests():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    class RetrySession(MockSession):
        def __init__(self):
            super().__init__()
            self.rate_limited = False

        def get(self, url, headers=None, timeout=30):
            if url.endswith("/d10k.htm") and not self.rate_limited:
                self.rate_limited = True
                self.calls.append(url)
                return MockResponse(status_code=429, headers={"Retry-After": "0"})
            return super().get(url, headers=headers, timeout=timeout)

    sleeps = []
    session = RetrySession()
    svc = SecEdgarIngestionService(
        repository=repo,
        session=session,
        fetch_config=FetchConfig(max_retries=2, backoff_seconds=0),
        sleep_func=sleeps.append,
    )

    result = svc.ingest(["AAPL"], forms=("10-K",), max_filings_per_ticker=1)

    assert result["processed"] == 1
    assert result["inserted"] == 1
    assert result["failed_fetch"] == 0
    assert result["retry_count"] == 1
    assert sleeps == [0.0]


def test_sec_ingestion_records_failed_fetch_and_continues():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    class FailingFilingSession(MockSession):
        def get(self, url, headers=None, timeout=30):
            if url.endswith("/d10k.htm"):
                self.calls.append(url)
                return MockResponse(status_code=404)
            return super().get(url, headers=headers, timeout=timeout)

    svc = SecEdgarIngestionService(repository=repo, session=FailingFilingSession())

    result = svc.ingest(["AAPL"], forms=("10-K",), max_filings_per_ticker=1)

    assert result["processed"] == 1
    assert result["inserted"] == 0
    assert result["failed_fetch"] == 1


def test_sec_ingestion_resolves_dynamic_ticker_to_cik():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    class DynamicTickerSession(MockSession):
        def get(self, url, headers=None, timeout=30):
            self.calls.append(url)
            if url.endswith("/company_tickers.json"):
                return MockResponse(
                    json_data={
                        "0": {"cik_str": 1321655, "ticker": "PLTR", "title": "Palantir Technologies Inc."}
                    }
                )
            if "submissions/CIK0001321655.json" in url:
                return MockResponse(
                    json_data={
                        "filings": {
                            "recent": {
                                "form": ["10-K"],
                                "accessionNumber": ["0001321655-24-000001"],
                                "primaryDocument": ["pltr-10k.htm"],
                                "filingDate": ["2024-02-20"],
                            }
                        }
                    }
                )
            if url.endswith("/pltr-10k.htm"):
                return MockResponse(text_data="<html><body>Revenue grew for Palantir.</body></html>")
            return MockResponse(status_code=404)

    SecEdgarIngestionService._company_ticker_cache = None
    session = DynamicTickerSession()
    svc = SecEdgarIngestionService(repository=repo, session=session)

    result = svc.ingest(["PLTR"], forms=("10-K",), max_filings_per_ticker=1)

    assert result["inserted"] == 1
    assert svc.ticker_to_cik["PLTR"] == "0001321655"
    assert repo.count_documents_by_ticker("PLTR") == 1
