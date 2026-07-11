"""One-command SEC filing ingestion for RAG evidence store.

Run from project root:
    python -m simulator.rag.run_sec_ingestion --db sqlite:///rag.db --tickers AAPL MSFT
"""
from __future__ import annotations

import argparse

from .repository import RagRepository
from .sec_ingestion import SecEdgarIngestionService
from .embeddings import (
    DeterministicFakeEmbeddingService,
    get_openai_embedding_service_from_env,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="SEC ingestion runner for RAG")
    parser.add_argument("--db", default="sqlite:///rag.db", help="SQLAlchemy DB URL")
    parser.add_argument("--tickers", nargs="+", default=["AAPL", "MSFT", "NVDA"], help="Ticker symbols")
    parser.add_argument("--max-filings", type=int, default=2, help="Max filings per ticker")
    parser.add_argument("--forms", nargs="+", default=["10-K", "10-Q", "8-K"], help="SEC form types")
    args = parser.parse_args()

    repo = RagRepository(args.db)
    repo.create_tables()

    svc = SecEdgarIngestionService(repository=repo)
    result = svc.ingest(
        tickers=args.tickers,
        forms=args.forms,
        max_filings_per_ticker=args.max_filings,
    )
    print(f"Ingestion complete: processed={result['processed']} inserted={result['inserted']}")

    emb = get_openai_embedding_service_from_env() or DeterministicFakeEmbeddingService()
    updated = repo.embed_missing_chunks(emb)
    print(f"Embeddings updated for {updated} chunk(s)")


if __name__ == "__main__":
    main()
