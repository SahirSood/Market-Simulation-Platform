import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from simulator.rag.monitor import detect_new_filings_for_ciks, fetch_latest_submissions_for_cik
from simulator.rag.repository import RagRepository


class MockResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_repository_returns_latest_accession_for_cik():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    repo.add_document_with_chunks(
        ticker="AAPL",
        title="Older filing",
        source_url="http://example.com/old",
        content="older content",
        chunks=[{"content": "older content", "start_pos": 0, "end_pos": 13}],
        cik="0000320193",
        accession_no="0000320193-24-000001",
        published_at=datetime(2024, 1, 1),
    )
    repo.add_document_with_chunks(
        ticker="AAPL",
        title="Newer filing",
        source_url="http://example.com/new",
        content="newer content",
        chunks=[{"content": "newer content", "start_pos": 0, "end_pos": 13}],
        cik="0000320193",
        accession_no="0000320193-24-000002",
        published_at=datetime(2024, 2, 1),
    )

    assert repo.get_latest_accession_for_cik("0000320193") == "0000320193-24-000002"
    assert repo.get_latest_accession_for_cik("320193") == "0000320193-24-000002"
    assert repo.get_latest_accession_for_cik("0000000000") is None


def test_detect_new_filings_stops_at_local_accession(monkeypatch):
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000320193-24-000003",
                    "0000320193-24-000002",
                    "0000320193-24-000001",
                ],
                "form": ["10-Q", "10-Q", "8-K"],
                "filingDate": ["2024-03-01", "2024-02-01", "2024-01-01"],
                "primaryDocument": ["a.htm", "b.htm", "c.htm"],
            }
        }
    }

    def fake_get(*args, **kwargs):
        return MockResponse(json_data=payload)

    monkeypatch.setattr("simulator.rag.monitor.requests.get", fake_get)

    class Repo:
        def get_latest_accession_for_cik(self, cik):
            return "0000320193-24-000002"

    results = detect_new_filings_for_ciks(["0000320193"], rag_repository=Repo(), max_items=5)
    assert list(results.keys()) == ["0000320193"]
    assert len(results["0000320193"]) == 1
    assert results["0000320193"][0]["accessionNumber"] == "0000320193-24-000003"


def test_fetch_latest_submissions_returns_trimmed_results(monkeypatch):
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["1", "2"],
                "form": ["10-K", "8-K"],
                "filingDate": ["2024-01-01", "2024-02-01"],
                "primaryDocument": ["a.htm", "b.htm"],
            }
        }
    }

    def fake_get(*args, **kwargs):
        return MockResponse(json_data=payload)

    monkeypatch.setattr("simulator.rag.monitor.requests.get", fake_get)
    items = fetch_latest_submissions_for_cik("320193", max_items=1)
    assert len(items) == 1
    assert items[0]["accessionNumber"] == "1"
