"""Lightweight poller that checks for new SEC filings and runs ingestion.

Usage:
    python scripts/ingest_poller.py --db sqlite:///rag.db --tickers AAPL MSFT --once
"""
from __future__ import annotations

import argparse
import logging
import time
from typing import Dict, List, Optional

from simulator.rag.monitor import detect_new_filings_for_ciks
from simulator.rag.repository import RagRepository
from simulator.rag.sec_ingestion import SecEdgarIngestionService

LOGGER = logging.getLogger(__name__)


def poll_and_ingest_once(
    tickers: List[str],
    db_url: str,
    max_filings: int,
    forms: List[str],
    repository: Optional[RagRepository] = None,
    ingestion_service: Optional[SecEdgarIngestionService] = None,
) -> Dict[str, object]:
    repo = repository or RagRepository(db_url)
    repo.create_tables()

    svc = ingestion_service or SecEdgarIngestionService(repository=repo)
    ticker_to_cik = svc.ticker_to_cik
    tracked_ciks = []
    unknown_tickers = []
    for ticker in tickers:
        symbol = ticker.upper()
        cik = ticker_to_cik.get(symbol)
        if cik:
            tracked_ciks.append(cik)
        else:
            unknown_tickers.append(symbol)

    if unknown_tickers:
        LOGGER.warning("No CIK mapping configured for: %s", ", ".join(unknown_tickers))

    detected = detect_new_filings_for_ciks(tracked_ciks, rag_repository=repo, max_items=max_filings)

    updated: List[str] = []
    for ticker in tickers:
        cik = ticker_to_cik.get(ticker.upper())
        if not cik:
            continue
        if detected.get(cik):
            LOGGER.info("New SEC filing detected for %s; starting ingestion", ticker.upper())
            svc.ingest([ticker], forms=tuple(forms), max_filings_per_ticker=max_filings)
            updated.append(ticker.upper())

    return {
        "tracked_ciks": tracked_ciks,
        "unknown_tickers": unknown_tickers,
        "detected": detected,
        "updated_tickers": updated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll SEC filings and ingest new ones")
    parser.add_argument("--db", default="sqlite:///rag.db", help="SQLAlchemy DB URL")
    parser.add_argument("--tickers", nargs="+", default=["AAPL", "MSFT", "NVDA"], help="Tracked tickers")
    parser.add_argument("--max-filings", type=int, default=2, help="Max filings to inspect per ticker")
    parser.add_argument("--forms", nargs="+", default=["10-K", "10-Q", "8-K"], help="SEC form types")
    parser.add_argument("--interval-seconds", type=int, default=3600, help="Sleep between polling cycles")
    parser.add_argument("--once", action="store_true", help="Run a single poll cycle and exit")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.once:
        print(poll_and_ingest_once(args.tickers, args.db, args.max_filings, args.forms))
        return

    try:
        while True:
            print(poll_and_ingest_once(args.tickers, args.db, args.max_filings, args.forms))
            time.sleep(max(1, args.interval_seconds))
    except KeyboardInterrupt:
        LOGGER.info("Poller stopped")


if __name__ == "__main__":
    main()
