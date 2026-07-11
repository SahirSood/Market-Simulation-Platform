import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from simulator.rag.repository import RagRepository


def test_add_and_query_document_and_chunks():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    content = "This is a sample 10-K transcript for TICKER. Section 1: Overview. Section 2: Financials."
    chunks = [
        {"content": "Section 1: Overview." , "start_pos": 0, "end_pos": 24},
        {"content": "Section 2: Financials.", "start_pos": 25, "end_pos": 50}
    ]

    doc = repo.add_document_with_chunks(ticker="TICKER", title="Sample Filing", source_url="http://example.com/1", content=content, chunks=chunks)
    assert doc is not None
    assert doc.ticker == "TICKER"

    found_chunks = repo.get_chunks_by_ticker("TICKER")
    assert len(found_chunks) == 2

    # keyword search
    results = repo.search_chunks("Financials")
    assert len(results) >= 1

    # deduplication: adding same content should return existing doc
    doc2 = repo.add_document_with_chunks(ticker="TICKER", title="Sample Filing", source_url="http://example.com/1", content=content, chunks=chunks)
    assert doc2.id == doc.id
