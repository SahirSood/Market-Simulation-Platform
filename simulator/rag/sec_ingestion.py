from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Dict, Iterable, List, Optional, Sequence

import requests

from .repository import RagRepository


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


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


class SecEdgarIngestionService:
    """Small SEC ingestion MVP for 10-K/10-Q/8-K filings."""

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
        user_agent: str = "MarketSimulationPlatform/1.0 (owner@example.com)",
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        ticker_to_cik: Optional[Dict[str, str]] = None,
    ):
        self.repository = repository
        self.session = session or requests.Session()
        self.user_agent = user_agent
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ticker_to_cik = ticker_to_cik or dict(self.DEFAULT_TICKER_TO_CIK)

    def ingest(
        self,
        tickers: Sequence[str],
        forms: Sequence[str] = ("10-K", "10-Q", "8-K"),
        max_filings_per_ticker: int = 3,
    ) -> Dict[str, int]:
        inserted = 0
        processed = 0

        for ticker in tickers:
            cik = self.ticker_to_cik.get(ticker.upper())
            if not cik:
                continue

            records = self._fetch_recent_filing_records(cik, forms=forms, max_items=max_filings_per_ticker)
            for record in records:
                processed += 1
                filing_url = self._build_filing_url(cik, record.accession_no, record.primary_document)
                filing_text_raw = self._fetch_text(filing_url)
                filing_text = self.clean_text(filing_text_raw)
                if not filing_text:
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
                )
                after_count = self.repository.count_documents()
                if after_count > before_count:
                    inserted += 1

        return {"processed": processed, "inserted": inserted}

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
        response = self.session.get(url, headers={"User-Agent": self.user_agent}, timeout=30)
        response.raise_for_status()
        return response.json()

    def _fetch_text(self, url: str) -> str:
        response = self.session.get(url, headers={"User-Agent": self.user_agent}, timeout=30)
        response.raise_for_status()
        return response.text

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
        text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
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
