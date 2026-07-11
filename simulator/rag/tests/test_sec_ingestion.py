import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from simulator.rag.repository import RagRepository
from simulator.rag.sec_ingestion import SecEdgarIngestionService


class MockResponse:
    def __init__(self, json_data=None, text_data="", status_code=200):
        self._json_data = json_data
        self.text = text_data
        self.status_code = status_code

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
    assert repo.count_documents() == 2
    assert repo.count_chunks() >= 2

    # Repeat run should not duplicate due to content hash deduplication
    result_2 = svc.ingest(["AAPL"], forms=("10-K", "10-Q", "8-K"), max_filings_per_ticker=3)
    assert result_2["processed"] == 2
    assert result_2["inserted"] == 0
    assert repo.count_documents() == 2

    chunks = repo.get_chunks_by_ticker("AAPL", limit=10)
    assert len(chunks) > 0
