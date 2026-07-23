import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from api import server


class CountOnlyRepo:
    def __init__(self, count):
        self.count = count

    def count_documents(self):
        return self.count


def test_rag_bootstrap_tops_up_underfilled_supported_tickers(monkeypatch):
    monkeypatch.setattr(server, "RAG_BOOTSTRAP_ON_STARTUP", True)
    monkeypatch.setattr(server, "RAG_BOOTSTRAP_TICKERS", ("AAPL", "MSFT", "SPY"))
    monkeypatch.setattr(server, "RAG_BOOTSTRAP_MAX_FILINGS", 2)

    assert server._rag_bootstrap_target_count() == 4
    assert server._rag_bootstrap_needed(CountOnlyRepo(3)) is True
    assert server._rag_bootstrap_needed(CountOnlyRepo(4)) is False


def test_rag_bootstrap_disabled_does_not_top_up(monkeypatch):
    monkeypatch.setattr(server, "RAG_BOOTSTRAP_ON_STARTUP", False)
    monkeypatch.setattr(server, "RAG_BOOTSTRAP_TICKERS", ("AAPL",))
    monkeypatch.setattr(server, "RAG_BOOTSTRAP_MAX_FILINGS", 2)

    assert server._rag_bootstrap_needed(CountOnlyRepo(0)) is False
