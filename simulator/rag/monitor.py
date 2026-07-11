"""Utilities for detecting new SEC filings."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
DEFAULT_USER_AGENT = os.getenv("SEC_USER_AGENT", "MarketSimulationPlatform/1.0 owner@example.com")
_LOG = logging.getLogger(__name__)


def _normalize_cik(cik: str) -> str:
    return str(cik).strip().zfill(10)


def fetch_latest_submissions_for_cik(cik: str, max_items: int = 5) -> List[Dict[str, Any]]:
    url = SEC_SUBMISSIONS_URL.format(cik=_normalize_cik(cik))
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    payload = response.json()

    recent = payload.get("filings", {}).get("recent", {})
    accession_numbers = recent.get("accessionNumber", [])
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    results: List[Dict[str, Any]] = []
    count = min(max_items, len(accession_numbers), len(forms), len(filing_dates), len(primary_docs))
    for idx in range(count):
        results.append(
            {
                "accessionNumber": accession_numbers[idx],
                "form": forms[idx],
                "filingDate": filing_dates[idx],
                "primaryDocument": primary_docs[idx],
            }
        )
    return results


def detect_new_filings_for_ciks(
    ciks: List[str],
    rag_repository: Optional[object] = None,
    max_items: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    results: Dict[str, List[Dict[str, Any]]] = {}
    for cik in ciks:
        normalized_cik = _normalize_cik(cik)
        try:
            remote_items = fetch_latest_submissions_for_cik(normalized_cik, max_items=max_items)
        except Exception as exc:
            _LOG.warning("Failed to fetch SEC submissions for %s: %s", normalized_cik, exc)
            results[normalized_cik] = []
            continue

        last_local = None
        if rag_repository is not None:
            getter = getattr(rag_repository, "get_latest_accession_for_cik", None)
            if callable(getter):
                try:
                    last_local = getter(normalized_cik)
                except Exception as exc:
                    _LOG.warning("Failed to read latest accession for %s: %s", normalized_cik, exc)

        new_items: List[Dict[str, Any]] = []
        for item in remote_items:
            accession = item.get("accessionNumber")
            if not accession:
                continue
            if last_local is None:
                new_items.append(item)
            elif accession == last_local:
                break
            else:
                new_items.append(item)

        results[normalized_cik] = new_items

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check SEC submissions for new filings")
    parser.add_argument("--ciks", nargs="+", required=True, help="Tracked CIKs")
    parser.add_argument("--max", type=int, default=5, help="Max recent filings per CIK")
    args = parser.parse_args()

    for cik, items in detect_new_filings_for_ciks(args.ciks, rag_repository=None, max_items=args.max).items():
        print(f"CIK {cik}: {len(items)} new filing(s)")
        for item in items:
            print(f"  - {item.get('accessionNumber')} {item.get('form')} {item.get('filingDate')}")
