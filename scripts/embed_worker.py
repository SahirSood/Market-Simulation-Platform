"""Batch embedding worker for RAG chunks missing embeddings.

This intentionally uses the database as the first worker queue: chunks with an
empty embedding are pending jobs, and setting the embedding marks them done.
It can later be swapped for Redis/RQ or Celery without changing repository
semantics.
"""
from __future__ import annotations

import argparse
import logging
import time

from simulator.rag.embeddings import get_openai_embedding_service_from_env
from simulator.rag.repository import RagRepository


LOGGER = logging.getLogger(__name__)


def embed_once(db_url: str, limit: int, batch_size: int, repository=None, embedding_service=None) -> int:
    repo = repository or RagRepository(db_url)
    repo.create_tables()
    service = embedding_service or get_openai_embedding_service_from_env()
    if service is None or not service.is_available():
        LOGGER.warning("Embedding service unavailable; no chunks embedded")
        return 0
    return repo.embed_missing_chunks(service, limit=limit, batch_size=batch_size)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed RAG chunks in batches")
    parser.add_argument("--db", default="sqlite:///rag.db", help="SQLAlchemy DB URL")
    parser.add_argument("--limit", type=int, default=1000, help="Max chunks per cycle")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Sleep between cycles")
    parser.add_argument("--once", action="store_true", help="Run one embedding cycle and exit")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.once:
        print({"embedded": embed_once(args.db, args.limit, args.batch_size)})
        return

    try:
        while True:
            embedded = embed_once(args.db, args.limit, args.batch_size)
            print({"embedded": embedded})
            time.sleep(max(1, args.interval_seconds))
    except KeyboardInterrupt:
        LOGGER.info("Embedding worker stopped")


if __name__ == "__main__":
    main()
