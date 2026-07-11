from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html
import logging
import os
import re
import time
from typing import Callable, Dict, List, Optional, Sequence

import requests

from .repository import RagRepository


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
DEFAULT_USER_AGENT = os.getenv("SEC_USER_AGENT", "MarketSimulationPlatform/1.0 owner@example.com")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
LOGGER = logging.getLogger(__name__)


def _parse_filing_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


@dataclass
class FilingRecord:
    form: str
    accession_no: str
    primary_document: str
    filing_date: Optional[datetime]


@dataclass
class FetchConfig:
    timeout_seconds: int = 30
    max_retries: int = 3
    backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0


class SecEdgarIngestionService:
    """SEC ingestion service for 10-K/10-Q/8-K filings."""

    DEFAULT_TICKER_TO_CIK: Dict[str, str] = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
        "NVDA": "0001045810",
        "TSLA": "0001318605",
        "AMZN": "0001018724",
        "GOOGL": "0001652044",
        "META": "0001326801",
    }

    def __init__(
        self,
        repository: RagRepository,
        session: Optional[requests.Session] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        ticker_to_cik: Optional[Dict[str, str]] = None,
        fetch_config: Optional[FetchConfig] = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ):
        self.repository = repository
        self.session = session or requests.Session()
        self.user_agent = user_agent
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ticker_to_cik = ticker_to_cik or dict(self.DEFAULT_TICKER_TO_CIK)
        self.fetch_config = fetch_config or FetchConfig()
        self._sleep = sleep_func
        self._retry_count = 0

    def ingest(
        self,
        tickers: Sequence[str],
        forms: Sequence[str] = ("10-K", "10-Q", "8-K"),
        max_filings_per_ticker: int = 3,
    ) -> Dict[str, int]:
        inserted = 0
        processed = 0
        skipped_duplicate = 0
        failed_fetch = 0
        last_successful_accession_by_cik: Dict[str, str] = {}
        self._retry_count = 0

        for ticker in tickers:
            cik = self.ticker_to_cik.get(ticker.upper())
            if not cik:
                continue

            try:
                records = self._fetch_recent_filing_records(cik, forms=forms, max_items=max_filings_per_ticker)
            except Exception as exc:
                failed_fetch += 1
                LOGGER.warning("Failed to fetch recent SEC records for %s: %s", ticker.upper(), exc)
                continue

            for record in records:
                processed += 1
                filing_url = self._build_filing_url(cik, record.accession_no, record.primary_document)
                try:
                    filing_text_raw = self._fetch_text(filing_url)
                except Exception as exc:
                    failed_fetch += 1
                    LOGGER.warning(
                        "Failed to fetch SEC filing %s for %s: %s",
                        record.accession_no,
                        ticker.upper(),
                        exc,
                    )
                    continue

                filing_text = self.clean_text(filing_text_raw)
                if not filing_text:
                    failed_fetch += 1
                    continue

                chunks = self.chunk_text(filing_text)
                before_count = self.repository.count_documents()
                self.repository.add_document_with_chunks(
                    ticker=ticker.upper(),
                    title=f"{ticker.upper()} {record.form} {record.filing_date.date() if record.filing_date else ''}".strip(),
                    source_url=filing_url,
                    content=filing_text,
                    chunks=chunks,
                    source_type="sec_filing",
                    source_name="SEC EDGAR",
                    form_type=record.form,
                    cik=cik,
                    accession_no=record.accession_no,
                    published_at=record.filing_date,
                    raw_content=filing_text_raw,
                )
                after_count = self.repository.count_documents()
                if after_count > before_count:
                    inserted += 1
                    last_successful_accession_by_cik[cik] = record.accession_no
                else:
                    skipped_duplicate += 1

        return {
            "processed": processed,
            "inserted": inserted,
            "skipped_duplicate": skipped_duplicate,
            "failed_fetch": failed_fetch,
            "retry_count": self._retry_count,
            "last_successful_accession_by_cik": last_successful_accession_by_cik,
        }

    def _fetch_recent_filing_records(
        self,
        cik: str,
        forms: Sequence[str],
        max_items: int,
    ) -> List[FilingRecord]:
        url = SEC_SUBMISSIONS_URL.format(cik=cik)
        payload = self._fetch_json(url)
        recent = payload.get("filings", {}).get("recent", {})
        form_arr = recent.get("form", [])
        accession_arr = recent.get("accessionNumber", [])
        primary_doc_arr = recent.get("primaryDocument", [])
        filing_date_arr = recent.get("filingDate", [])

        records: List[FilingRecord] = []
        wanted = set(forms)
        n = min(len(form_arr), len(accession_arr), len(primary_doc_arr), len(filing_date_arr))
        for i in range(n):
            form = form_arr[i]
            if form not in wanted:
                continue
            record = FilingRecord(
                form=form,
                accession_no=accession_arr[i],
                primary_document=primary_doc_arr[i],
                filing_date=_parse_filing_date(filing_date_arr[i]),
            )
            records.append(record)
            if len(records) >= max_items:
                break
        return records

    def _fetch_json(self, url: str) -> dict:
        response = self._request_with_retries(url)
        return response.json()

    def _fetch_text(self, url: str) -> str:
        response = self._request_with_retries(url)
        return response.text

    def _request_with_retries(self, url: str):
        last_exc: Optional[BaseException] = None
        attempts = self.fetch_config.max_retries + 1
        for attempt in range(attempts):
            try:
                response = self.session.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    timeout=self.fetch_config.timeout_seconds,
                )
                status_code = getattr(response, "status_code", 200)
                if status_code not in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response

                last_exc = RuntimeError(f"HTTP {status_code}")
                if attempt >= attempts - 1:
                    response.raise_for_status()
                    raise last_exc

                self._sleep(self._retry_delay(attempt, response=response))
                self._retry_count += 1
                continue

            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    raise
                self._sleep(self._retry_delay(attempt))
                self._retry_count += 1

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Failed to fetch {url}")

    def _retry_delay(self, attempt: int, response=None) -> float:
        retry_after = None
        headers = getattr(response, "headers", None)
        if headers:
            retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), self.fetch_config.max_backoff_seconds)
            except ValueError:
                pass
        delay = self.fetch_config.backoff_seconds * (2 ** attempt)
        return min(delay, self.fetch_config.max_backoff_seconds)

    @staticmethod
    def _build_filing_url(cik: str, accession_no: str, primary_document: str) -> str:
        accession_compact = accession_no.replace("-", "")
        cik_no_leading_zeros = str(int(cik))
        return f"{SEC_ARCHIVES_BASE}/{cik_no_leading_zeros}/{accession_compact}/{primary_document}"

    @staticmethod
    def clean_text(raw_text: str) -> str:
        if not raw_text:
            return ""
        text = re.sub(r"<script.*?>.*?</script>", " ", raw_text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def chunk_text(self, text: str) -> List[dict]:
        if not text:
            return []
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        chunks: List[dict] = []
        start = 0
        step = self.chunk_size - self.chunk_overlap
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            content = text[start:end].strip()
            if content:
                chunks.append({"content": content, "start_pos": start, "end_pos": end})
            if end >= len(text):
                break
            start += step
        return chunks
