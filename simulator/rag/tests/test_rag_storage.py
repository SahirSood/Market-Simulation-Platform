import os
import sys
from datetime import datetime

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


def test_get_chunks_by_ids_returns_document_metadata_in_requested_order():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    doc = repo.add_document_with_chunks(
        ticker="AAPL",
        title="Apple 10-Q",
        source_url="https://example.com/aapl-10q",
        content="risk factors gross margin revenue",
        chunks=[
            {"content": "risk factors", "start_pos": 0, "end_pos": 12},
            {"content": "gross margin revenue", "start_pos": 13, "end_pos": 33},
        ],
        source_type="sec",
        source_name="SEC EDGAR",
        form_type="10-Q",
        cik="320193",
        accession_no="0000320193-26-000001",
        published_at=datetime(2026, 1, 1),
    )
    chunks = repo.get_chunks_by_ticker("AAPL")
    requested_ids = [chunks[0].id, chunks[1].id]

    rows = repo.get_chunks_by_ids(requested_ids)

    assert [row["chunk_id"] for row in rows] == requested_ids
    assert rows[0]["document_id"] == doc.id
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["form_type"] == "10-Q"
    assert rows[0]["cik"] == "0000320193"
    assert rows[0]["accession_no"] == "0000320193-26-000001"
    assert rows[0]["source_url"] == "https://example.com/aapl-10q"


def test_document_catalog_lists_facets_and_bounded_detail():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    doc = repo.add_document_with_chunks(
        ticker="MSFT",
        title="Microsoft 8-K",
        source_url="https://example.com/msft-8k",
        content="event filing about cloud revenue and risk factors",
        chunks=[
            {"content": "event filing about cloud revenue", "start_pos": 0, "end_pos": 32},
            {"content": "risk factors", "start_pos": 33, "end_pos": 45},
        ],
        source_type="sec_filing",
        source_name="SEC EDGAR",
        form_type="8-K",
        cik="789019",
        accession_no="0000789019-26-000001",
        published_at=datetime(2026, 2, 1),
    )

    summary = repo.summarize_documents()
    listed = repo.list_documents(ticker="MSFT", form_type="8-K")
    detail = repo.get_document_detail(doc.id, chunk_limit=1)
    chunk_ids = repo.get_document_chunk_id_map([doc.id])

    assert summary["document_count"] == 1
    assert summary["chunk_count"] == 2
    assert summary["tickers"] == [{"value": "MSFT", "count": 1}]
    assert listed["total"] == 1
    assert listed["documents"][0]["content_preview"] == "event filing about cloud revenue and risk factors"
    assert detail["chunk_count"] == 2
    assert len(detail["chunks"]) == 1
    assert len(chunk_ids[doc.id]) == 2
    assert detail["chunks"][0]["chunk_id"] in chunk_ids[doc.id]
    assert repo.count_documents_by_ticker("MSFT") == 1


def test_rag_job_status_records_attempts_and_metadata():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    job_id = repo.start_job("embedding", metadata={"limit": 10}, max_attempts=2)
    repo.update_job_status(job_id, "running", attempts=1)
    repo.update_job_status(job_id, "succeeded", attempts=2, metadata={"embedded": 3})

    rows = repo.list_job_status("embedding")

    assert rows[0]["status"] == "succeeded"
    assert rows[0]["attempts"] == 2
    assert rows[0]["max_attempts"] == 2
    assert rows[0]["metadata"]["limit"] == 10
    assert rows[0]["metadata"]["embedded"] == 3


def test_rag_job_status_summary_and_requeue():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    failed_id = repo.start_job("embedding", metadata={"limit": 10}, max_attempts=2)
    repo.update_job_status(failed_id, "failed", attempts=2, error="rate limit")
    succeeded_id = repo.start_job("ingestion", metadata={"tickers": ["AAPL"]}, max_attempts=1)
    repo.update_job_status(succeeded_id, "succeeded", attempts=1)

    summary = repo.summarize_job_status()

    assert summary["total"] == 2
    assert summary["by_type"]["embedding"]["failed"] == 1
    assert summary["by_type"]["ingestion"]["succeeded"] == 1

    requeued = repo.requeue_jobs(job_type="embedding", limit=5)

    assert len(requeued) == 1
    assert requeued[0]["id"] == failed_id
    assert requeued[0]["status"] == "queued"
    assert requeued[0]["last_error"] is None
    assert requeued[0]["metadata"]["previous_status"] == "failed"

    updated_summary = repo.summarize_job_status()
    assert updated_summary["by_type"]["embedding"]["queued"] == 1
