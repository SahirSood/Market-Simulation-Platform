"""Build a timestamped historical context file for replay generation.

The output is a local ``--news-file`` input for
``scripts/build_historical_replay_events.py``. It combines:

- an existing macro/calendar context file
- SEC EDGAR company filing metadata
- NewsAPI article metadata, when NEWS_API_KEY is configured and the plan allows it

Only metadata available at or before the replay timestamp should be included.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import zipfile
from collections import Counter
from datetime import date, datetime, time as dt_time, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Iterable, Mapping
from urllib.parse import unquote, urlparse

import requests
from dotenv import load_dotenv


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
GDELT_GKG_URL_TEMPLATE = "http://data.gdeltproject.org/gdeltv2/{timestamp}.gkg.csv.zip"

DEFAULT_SEC_FORMS = ["10-K", "10-Q", "8-K", "20-F", "6-K"]
DEFAULT_USER_AGENT = "MarketSimulationPlatform/1.0 research@example.com"
DEFAULT_NEWSAPI_DOMAINS = (
    "finance.yahoo.com,cnbc.com,reuters.com,bloomberg.com,marketwatch.com,"
    "barrons.com,benzinga.com,seekingalpha.com,fool.com,businesswire.com,"
    "prnewswire.com,globenewswire.com,thefly.com,thestreet.com,barchart.com"
)
AMBIGUOUS_NEWSAPI_TICKERS = {"BA", "C", "CAT", "DE", "GE", "HD", "KO", "MA", "MS", "NOW", "T", "V"}
AMBIGUOUS_TICKERS = {"BA", "C", "CAT", "DE", "GE", "HD", "KO", "MA", "MS", "NOW", "T", "V"}
DEFAULT_GDELT_TIMES_UTC = ["130000", "160000", "200000"]
DEFAULT_GDELT_DOMAINS = (
    "finance.yahoo.com,cnbc.com,reuters.com,bloomberg.com,marketwatch.com,"
    "barrons.com,benzinga.com,seekingalpha.com,fool.com,businesswire.com,"
    "prnewswire.com,globenewswire.com,thefly.com,thestreet.com,barchart.com,"
    "investing.com,investors.com,zacks.com,morningstar.com"
)
MARKET_RELEVANCE_TERMS = (
    "stock", "stocks", "share", "shares", "earnings", "revenue", "profit",
    "analyst", "upgrade", "downgrade", "price target", "dividend", "buyback",
    "merger", "acquisition", "guidance", "forecast", "quarterly", "q1", "q2",
    "q3", "q4", "wall street", "market", "investor", "sec filing",
)
COMPANY_ALIASES = {
    "AAPL": ["Apple"],
    "MSFT": ["Microsoft"],
    "NVDA": ["Nvidia", "NVIDIA"],
    "GOOGL": ["Alphabet", "Google"],
    "META": ["Meta", "Facebook"],
    "AMZN": ["Amazon"],
    "TSLA": ["Tesla"],
    "AVGO": ["Broadcom"],
    "AMD": ["Advanced Micro Devices"],
    "INTC": ["Intel"],
    "ORCL": ["Oracle"],
    "CRM": ["Salesforce"],
    "ADBE": ["Adobe"],
    "IBM": ["IBM", "International Business Machines"],
    "NFLX": ["Netflix"],
    "NOW": ["ServiceNow"],
    "PLTR": ["Palantir"],
    "JPM": ["JPMorgan", "JPMorgan Chase"],
    "BAC": ["Bank of America"],
    "WFC": ["Wells Fargo"],
    "GS": ["Goldman Sachs"],
    "MS": ["Morgan Stanley"],
    "C": ["Citigroup"],
    "V": ["Visa"],
    "MA": ["Mastercard"],
    "AXP": ["American Express"],
    "BLK": ["BlackRock"],
    "SCHW": ["Charles Schwab"],
    "LLY": ["Eli Lilly"],
    "UNH": ["UnitedHealth", "UnitedHealth Group"],
    "JNJ": ["Johnson & Johnson"],
    "ABBV": ["AbbVie"],
    "MRK": ["Merck"],
    "PFE": ["Pfizer"],
    "TMO": ["Thermo Fisher"],
    "ABT": ["Abbott"],
    "ISRG": ["Intuitive Surgical"],
    "AMGN": ["Amgen"],
    "WMT": ["Walmart"],
    "COST": ["Costco"],
    "HD": ["Home Depot"],
    "MCD": ["McDonald", "McDonald's"],
    "SBUX": ["Starbucks"],
    "NKE": ["Nike"],
    "DIS": ["Disney", "Walt Disney"],
    "KO": ["Coca-Cola", "Coca Cola"],
    "PEP": ["PepsiCo"],
    "PG": ["Procter & Gamble"],
    "XOM": ["Exxon", "ExxonMobil"],
    "CVX": ["Chevron"],
    "COP": ["ConocoPhillips"],
    "SLB": ["Schlumberger", "SLB"],
    "CAT": ["Caterpillar"],
    "DE": ["Deere"],
    "GE": ["GE Aerospace", "General Electric"],
    "BA": ["Boeing"],
    "LMT": ["Lockheed Martin"],
    "RTX": ["RTX", "Raytheon"],
    "UPS": ["UPS", "United Parcel Service"],
    "FDX": ["FedEx"],
    "CMCSA": ["Comcast"],
    "T": ["AT&T"],
    "VZ": ["Verizon"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build timestamped historical replay context from macro, SEC, and NewsAPI sources."
    )
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD.")
    parser.add_argument("--tickers", nargs="+", required=True, help="Company tickers to enrich.")
    parser.add_argument("--macro-file", default=None, help="Existing macro/context JSON to merge.")
    parser.add_argument("--output", required=True, help="Output news-file JSON path.")
    parser.add_argument("--report", default=None, help="Optional companion report path.")
    parser.add_argument("--include-sec", action="store_true", help="Fetch SEC EDGAR filing metadata.")
    parser.add_argument("--include-newsapi", action="store_true", help="Fetch NewsAPI article metadata.")
    parser.add_argument("--include-gdelt-gkg", action="store_true", help="Sample GDELT GKG archive files for public article URLs.")
    parser.add_argument(
        "--newsapi-start",
        default=None,
        help="Optional NewsAPI-only start date when the configured plan has a shorter archive window.",
    )
    parser.add_argument("--sec-forms", nargs="+", default=DEFAULT_SEC_FORMS)
    parser.add_argument("--sec-user-agent", default=os.getenv("SEC_USER_AGENT") or DEFAULT_USER_AGENT)
    parser.add_argument("--sec-pause-seconds", type=float, default=0.12)
    parser.add_argument("--newsapi-max-per-ticker", type=int, default=5)
    parser.add_argument("--newsapi-page-size", type=int, default=20)
    parser.add_argument("--newsapi-pause-seconds", type=float, default=0.25)
    parser.add_argument(
        "--newsapi-domains",
        default=DEFAULT_NEWSAPI_DOMAINS,
        help="Comma-separated domain allowlist for NewsAPI. Use an empty string to disable.",
    )
    parser.add_argument("--gdelt-times-utc", nargs="+", default=DEFAULT_GDELT_TIMES_UTC)
    parser.add_argument("--gdelt-domains", default=DEFAULT_GDELT_DOMAINS)
    parser.add_argument("--gdelt-max-per-ticker", type=int, default=80)
    parser.add_argument("--gdelt-max-total", type=int, default=2500)
    parser.add_argument("--gdelt-pause-seconds", type=float, default=0.05)
    parser.add_argument("--gdelt-fetch-page-titles", action="store_true")
    parser.add_argument("--gdelt-title-fetch-limit", type=int, default=300)
    parser.add_argument("--gdelt-title-pause-seconds", type=float, default=0.2)
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    start_dt = datetime.combine(start, dt_time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, dt_time.max, tzinfo=timezone.utc)
    tickers = _normalize_tickers(args.tickers)

    headlines: list[dict] = []
    source_reports = {}
    sources = []

    if args.macro_file:
        macro_rows, macro_sources = load_context_file(args.macro_file)
        headlines.extend(macro_rows)
        sources.extend(macro_sources)
        source_reports["macro_file"] = {
            "path": str(args.macro_file),
            "headline_count": len(macro_rows),
        }

    company_map = {}
    if args.include_sec or args.include_newsapi or args.include_gdelt_gkg:
        company_map = fetch_sec_company_map(args.sec_user_agent)

    if args.include_sec:
        sec_rows, sec_report = fetch_sec_context(
            tickers,
            company_map,
            start_dt,
            end_dt,
            forms={form.upper() for form in args.sec_forms},
            user_agent=args.sec_user_agent,
            pause_seconds=max(0.0, args.sec_pause_seconds),
        )
        headlines.extend(sec_rows)
        source_reports["sec_edgar"] = sec_report
        sources.append({
            "name": "SEC EDGAR submissions API",
            "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        })

    if args.include_newsapi:
        newsapi_start = date.fromisoformat(args.newsapi_start) if args.newsapi_start else start
        news_rows, news_report = fetch_newsapi_context(
            tickers,
            company_map,
            newsapi_start,
            end,
            max_per_ticker=max(0, args.newsapi_max_per_ticker),
            page_size=max(1, min(100, args.newsapi_page_size)),
            pause_seconds=max(0.0, args.newsapi_pause_seconds),
            domains=str(args.newsapi_domains or "").strip(),
        )
        headlines.extend(news_rows)
        source_reports["newsapi"] = news_report
        sources.append({
            "name": "NewsAPI Everything endpoint",
            "url": "https://newsapi.org/docs/endpoints/everything",
        })

    if args.include_gdelt_gkg:
        gdelt_rows, gdelt_report = fetch_gdelt_gkg_context(
            tickers,
            company_map,
            start,
            end,
            sample_times=args.gdelt_times_utc,
            domains=str(args.gdelt_domains or ""),
            max_per_ticker=max(0, args.gdelt_max_per_ticker),
            max_total=max(0, args.gdelt_max_total),
            pause_seconds=max(0.0, args.gdelt_pause_seconds),
            fetch_page_titles=bool(args.gdelt_fetch_page_titles),
            title_fetch_limit=max(0, args.gdelt_title_fetch_limit),
            title_pause_seconds=max(0.0, args.gdelt_title_pause_seconds),
            user_agent=args.sec_user_agent,
        )
        headlines.extend(gdelt_rows)
        source_reports["gdelt_gkg"] = gdelt_report
        sources.append({
            "name": "GDELT Global Knowledge Graph 2.1",
            "url": "https://www.gdeltproject.org/",
        })

    headlines = _dedupe_headlines(headlines)
    headlines.sort(key=lambda row: row["published_at"])
    output = {
        "name": f"Historical Replay Context {start.isoformat()} to {end.isoformat()}",
        "description": (
            "Timestamped replay context assembled from official macro calendars, "
            "SEC EDGAR filings, and NewsAPI metadata when available."
        ),
        "tickers": tickers,
        "sources": _dedupe_sources(sources),
        "headlines": headlines,
    }
    write_json(args.output, output)

    report = build_report(
        start=start,
        end=end,
        tickers=tickers,
        headlines=headlines,
        source_reports=source_reports,
    )
    if args.report:
        write_json(args.report, report)
    print(json.dumps({
        "output": args.output,
        "report": args.report,
        "ticker_count": len(tickers),
        "headline_count": len(headlines),
        "source_counts": report["source_counts"],
    }, indent=2))
    return 0


def load_context_file(path: str | Path) -> tuple[list[dict], list[dict]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        rows = payload.get("headlines") or payload.get("articles") or payload.get("events") or []
        sources = payload.get("sources") or []
    elif isinstance(payload, list):
        rows = payload
        sources = []
    else:
        raise ValueError(f"Unsupported context payload in {path}")
    normalized = []
    for row in rows:
        item = normalize_context_row(row, default_source="historical_context_file")
        if item:
            normalized.append(item)
    return normalized, [source for source in sources if isinstance(source, dict)]


def fetch_sec_company_map(user_agent: str) -> dict[str, dict]:
    response = requests.get(
        SEC_TICKERS_URL,
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    mapping = {}
    for row in payload.values():
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        mapping[ticker] = {
            "cik": str(row.get("cik_str")).zfill(10),
            "title": str(row.get("title") or ticker).strip(),
        }
    return mapping


def fetch_sec_context(
    tickers: list[str],
    company_map: Mapping[str, Mapping],
    start_dt: datetime,
    end_dt: datetime,
    *,
    forms: set[str],
    user_agent: str,
    pause_seconds: float,
) -> tuple[list[dict], dict]:
    rows = []
    errors = []
    tickers_with_filings = set()
    for ticker in tickers:
        company = company_map.get(ticker)
        if not company:
            errors.append({"ticker": ticker, "error": "ticker not found in SEC company_tickers.json"})
            continue
        try:
            filings = fetch_sec_submissions(
                ticker,
                company,
                start_dt,
                end_dt,
                forms=forms,
                user_agent=user_agent,
            )
            if filings:
                tickers_with_filings.add(ticker)
            rows.extend(filings)
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:300]})
        if pause_seconds:
            time.sleep(pause_seconds)
    return rows, {
        "tickers_attempted": len(tickers),
        "tickers_with_filings": len(tickers_with_filings),
        "headline_count": len(rows),
        "forms": sorted(forms),
        "errors": errors[:50],
        "error_count": len(errors),
    }


def fetch_sec_submissions(
    ticker: str,
    company: Mapping,
    start_dt: datetime,
    end_dt: datetime,
    *,
    forms: set[str],
    user_agent: str,
) -> list[dict]:
    cik = str(company["cik"]).zfill(10)
    response = requests.get(
        SEC_SUBMISSIONS_URL.format(cik=cik),
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    response.raise_for_status()
    recent = response.json().get("filings", {}).get("recent", {})
    form_rows = recent.get("form") or []
    output = []
    for index, form in enumerate(form_rows):
        form = str(form or "").upper().strip()
        if form not in forms:
            continue
        published_at = _sec_published_at(recent, index)
        if not published_at or published_at < start_dt or published_at > end_dt:
            continue
        accession_no = _list_value(recent, "accessionNumber", index)
        primary_doc = _list_value(recent, "primaryDocument", index)
        report_date = _list_value(recent, "reportDate", index)
        company_name = str(company.get("title") or ticker).strip()
        title = f"SEC filing: {company_name} files {form}"
        if report_date:
            title += f" for report date {report_date}"
        output.append({
            "title": title,
            "source": "SEC EDGAR",
            "published_at": _iso_z(published_at),
            "url": _sec_filing_url(cik, accession_no, primary_doc),
            "tickers": [ticker],
            "category": "company",
            "replay_source": "sec_edgar_submissions",
            "form": form,
            "cik": cik,
            "accession_no": accession_no,
        })
    return output


def fetch_newsapi_context(
    tickers: list[str],
    company_map: Mapping[str, Mapping],
    start: date,
    end: date,
    *,
    max_per_ticker: int,
    page_size: int,
    pause_seconds: float,
    domains: str,
) -> tuple[list[dict], dict]:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return [], {
            "enabled": False,
            "headline_count": 0,
            "error_count": 1,
            "errors": [{"error": "NEWS_API_KEY is not configured"}],
        }
    rows = []
    errors = []
    tickers_with_articles = set()
    for ticker in tickers:
        company_name = str((company_map.get(ticker) or {}).get("title") or ticker)
        query = newsapi_query(ticker, company_name)
        params = {
            "apiKey": api_key,
            "q": query,
            "searchIn": "title,description",
            "from": start.isoformat(),
            "to": end.isoformat(),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, max(max_per_ticker, 1)),
            "page": 1,
        }
        if domains:
            params["domains"] = domains
        try:
            response = requests.get(NEWSAPI_EVERYTHING_URL, params=params, timeout=30)
            payload = response.json()
            if response.status_code != 200 or payload.get("status") != "ok":
                error_row = {
                    "ticker": ticker,
                    "status_code": response.status_code,
                    "code": payload.get("code"),
                    "message": str(payload.get("message") or "")[:300],
                }
                errors.append(error_row)
                if _newsapi_fatal_error(error_row):
                    break
                if pause_seconds:
                    time.sleep(pause_seconds)
                continue
            articles = payload.get("articles") or []
            for article in articles[:max_per_ticker]:
                item = normalize_newsapi_article(article, ticker)
                if item:
                    rows.append(item)
            if articles:
                tickers_with_articles.add(ticker)
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:300]})
        if pause_seconds:
            time.sleep(pause_seconds)
    return rows, {
        "enabled": True,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "tickers_attempted": len(tickers),
        "tickers_with_articles": len(tickers_with_articles),
        "headline_count": len(rows),
        "max_per_ticker": max_per_ticker,
        "domains": domains,
        "errors": errors[:50],
        "error_count": len(errors),
    }


def fetch_gdelt_gkg_context(
    tickers: list[str],
    company_map: Mapping[str, Mapping],
    start: date,
    end: date,
    *,
    sample_times: list[str],
    domains: str,
    max_per_ticker: int,
    max_total: int,
    pause_seconds: float,
    fetch_page_titles: bool,
    title_fetch_limit: int,
    title_pause_seconds: float,
    user_agent: str,
) -> tuple[list[dict], dict]:
    aliases = build_ticker_aliases(tickers, company_map)
    allowed_domains = parse_domain_allowlist(domains)
    sample_times = normalize_gdelt_times(sample_times)
    rows = []
    errors = []
    files_attempted = 0
    files_downloaded = 0
    seen_urls = set()
    per_ticker_counts: Counter[str] = Counter()

    for current_day in iter_dates(start, end):
        for sample_time in sample_times:
            if max_total and len(rows) >= max_total:
                break
            timestamp = f"{current_day.strftime('%Y%m%d')}{sample_time}"
            files_attempted += 1
            try:
                file_rows = fetch_gdelt_gkg_file(
                    timestamp,
                    aliases,
                    allowed_domains,
                    max_per_ticker=max_per_ticker,
                    per_ticker_counts=per_ticker_counts,
                    seen_urls=seen_urls,
                    user_agent=user_agent,
                )
                files_downloaded += 1
                rows.extend(file_rows)
            except Exception as exc:
                errors.append({"timestamp": timestamp, "error": str(exc)[:300]})
            if pause_seconds:
                time.sleep(pause_seconds)
        if max_total and len(rows) >= max_total:
            break

    if max_total:
        rows = rows[:max_total]
    title_stats = {"attempted": 0, "updated": 0, "failed": 0}
    if fetch_page_titles and title_fetch_limit:
        title_stats = enrich_gdelt_page_titles(
            rows,
            limit=title_fetch_limit,
            pause_seconds=title_pause_seconds,
            user_agent=user_agent,
        )

    return rows, {
        "enabled": True,
        "headline_count": len(rows),
        "files_attempted": files_attempted,
        "files_downloaded": files_downloaded,
        "sample_times_utc": sample_times,
        "domains": sorted(allowed_domains),
        "matching_scope": "url_slug_and_url",
        "max_per_ticker": max_per_ticker,
        "max_total": max_total,
        "ticker_context_counts": dict(sorted(per_ticker_counts.items())),
        "title_fetch": title_stats,
        "errors": errors[:50],
        "error_count": len(errors),
    }


def fetch_gdelt_gkg_file(
    timestamp: str,
    aliases: Mapping[str, list[str]],
    allowed_domains: set[str],
    *,
    max_per_ticker: int,
    per_ticker_counts: Counter[str],
    seen_urls: set[str],
    user_agent: str,
) -> list[dict]:
    url = GDELT_GKG_URL_TEMPLATE.format(timestamp=timestamp)
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
    response.raise_for_status()
    output = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        name = archive.namelist()[0]
        for raw_line in archive.read(name).decode("utf-8", "replace").splitlines():
            item = gdelt_row_to_context(
                raw_line,
                aliases,
                allowed_domains,
                max_per_ticker=max_per_ticker,
                per_ticker_counts=per_ticker_counts,
                seen_urls=seen_urls,
            )
            if item:
                output.append(item)
    return output


def gdelt_row_to_context(
    raw_line: str,
    aliases: Mapping[str, list[str]],
    allowed_domains: set[str],
    *,
    max_per_ticker: int,
    per_ticker_counts: Counter[str],
    seen_urls: set[str],
) -> dict | None:
    cols = raw_line.split("\t")
    if len(cols) < 15:
        return None
    published_at = parse_gdelt_datetime(cols[1])
    source = str(cols[3] or "").strip()
    url = str(cols[4] or "").strip()
    if not published_at or not url or url in seen_urls:
        return None
    domain = normalized_domain(url)
    if allowed_domains and not domain_allowed(domain, allowed_domains):
        return None

    title = title_from_url(url)
    if not title:
        return None

    text_parts = [
        source,
        url,
        cols[8] if len(cols) > 8 else "",
        cols[13] if len(cols) > 13 else "",
        cols[14] if len(cols) > 14 else "",
        cols[23] if len(cols) > 23 else "",
    ]
    haystack = " ".join(text_parts).lower()
    title_haystack = f"{title} {url}".lower()
    matched_tickers = match_gdelt_tickers(title_haystack, aliases)
    if not matched_tickers:
        return None
    if not is_market_relevant(haystack):
        return None

    kept_tickers = []
    for ticker in matched_tickers:
        if max_per_ticker and per_ticker_counts[ticker] >= max_per_ticker:
            continue
        kept_tickers.append(ticker)
    if not kept_tickers:
        return None

    seen_urls.add(url)
    for ticker in kept_tickers:
        per_ticker_counts[ticker] += 1
    return {
        "title": title,
        "source": source or domain or "GDELT",
        "published_at": _iso_z(published_at),
        "url": url,
        "tickers": kept_tickers,
        "category": "company",
        "replay_source": "gdelt_gkg_sample",
        "title_source": "url_slug",
        "archive_source": "GDELT GKG 2.1",
    }


def enrich_gdelt_page_titles(
    rows: list[dict],
    *,
    limit: int,
    pause_seconds: float,
    user_agent: str,
) -> dict:
    attempted = updated = failed = 0
    for row in rows:
        if attempted >= limit:
            break
        attempted += 1
        try:
            title = fetch_page_title(row["url"], user_agent=user_agent)
            if title:
                row["title"] = title
                row["title_source"] = "page_title"
                updated += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        if pause_seconds:
            time.sleep(pause_seconds)
    return {"attempted": attempted, "updated": updated, "failed": failed}


def fetch_page_title(url: str, *, user_agent: str) -> str | None:
    response = requests.get(
        url,
        headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
        timeout=10,
        allow_redirects=True,
    )
    if response.status_code >= 400:
        return None
    text = response.text[:200000]
    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title[^>]*>(.*?)</title>",
    ):
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return clean_title(match.group(1))
    return None


def build_ticker_aliases(tickers: list[str], company_map: Mapping[str, Mapping]) -> dict[str, list[str]]:
    aliases = {}
    for ticker in tickers:
        rows = [ticker]
        company_name = str((company_map.get(ticker) or {}).get("title") or "").strip()
        if company_name:
            rows.extend(company_name_aliases(company_name))
        rows.extend(COMPANY_ALIASES.get(ticker, []))
        cleaned = []
        seen = set()
        for value in rows:
            alias = str(value or "").strip()
            if not alias:
                continue
            if alias.upper() == ticker and (ticker in AMBIGUOUS_TICKERS or len(ticker) <= 2):
                continue
            key = alias.lower()
            if len(key) < 3 and key.upper() != ticker:
                continue
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(alias)
        aliases[ticker] = cleaned
    return aliases


def company_name_aliases(company_name: str) -> list[str]:
    output = [company_name]
    cleaned = re.sub(
        r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|PLC|LTD|LIMITED|CLASS A|COMMON STOCK)\b\.?",
        "",
        company_name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    if cleaned and cleaned.lower() != company_name.lower():
        output.append(cleaned)
    return output


def match_gdelt_tickers(haystack: str, aliases: Mapping[str, list[str]]) -> list[str]:
    matched = []
    for ticker, values in aliases.items():
        for alias in values:
            needle = alias.lower()
            if needle.upper() == ticker and len(needle) <= 5:
                pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
                if re.search(pattern, haystack):
                    matched.append(ticker)
                    break
            elif needle in haystack:
                matched.append(ticker)
                break
    return matched


def is_market_relevant(text: str) -> bool:
    return any(term in text for term in MARKET_RELEVANCE_TERMS)


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return ""
    slug = unquote(path_parts[-1])
    slug = re.sub(r"\.(html?|aspx?|php|cms)$", "", slug, flags=re.IGNORECASE)
    slug = re.sub(r"[_\-]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip(" .-_")
    slug = re.sub(r"\b\d{6,}\b", "", slug).strip()
    return clean_title(slug)


def clean_title(title: str) -> str:
    value = unescape(re.sub(r"<[^>]+>", " ", str(title or "")))
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n-|")
    value = re.sub(r"\s+[-|]\s+(Yahoo Finance|CNBC|Reuters|Bloomberg|MarketWatch|Benzinga|TheStreet|Barchart).*$", "", value, flags=re.IGNORECASE)
    if len(value) > 240:
        value = value[:240].rsplit(" ", 1)[0]
    return value


def parse_gdelt_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if len(text) != 14 or not text.isdigit():
        return None
    try:
        return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalized_domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def parse_domain_allowlist(value: str) -> set[str]:
    return {
        normalized.lstrip(".")
        for raw in str(value or "").split(",")
        for normalized in [raw.strip().lower()]
        if normalized
    }


def domain_allowed(domain: str, allowed_domains: set[str]) -> bool:
    if not domain:
        return False
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def normalize_gdelt_times(values: Iterable[str]) -> list[str]:
    output = []
    for value in values:
        text = str(value).strip().replace(":", "")
        if len(text) == 4:
            text = f"{text}00"
        if len(text) != 6 or not text.isdigit():
            raise ValueError(f"Invalid GDELT sample time: {value}")
        minute = int(text[2:4])
        if minute % 15 != 0:
            raise ValueError("GDELT sample times must fall on 15-minute boundaries")
        output.append(text)
    return output


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _newsapi_fatal_error(error_row: Mapping) -> bool:
    code = str(error_row.get("code") or "").lower()
    message = str(error_row.get("message") or "").lower()
    if code in {"apikeydisabled", "apikeyexhausted", "apikeyinvalid", "ratelimited"}:
        return True
    return "too far in the past" in message or "upgrade" in message


def newsapi_query(ticker: str, company_name: str) -> str:
    cleaned_name = (
        company_name
        .replace(" INC.", "")
        .replace(" Inc.", "")
        .replace(" INCORPORATED", "")
        .replace(" CORP.", "")
        .replace(" CORP", "")
        .replace(" CO.", "")
        .replace(" CO", "")
        .strip()
    )
    if len(cleaned_name) > 60:
        cleaned_name = cleaned_name[:60].rsplit(" ", 1)[0]
    company_clause = f'"{cleaned_name}"'
    if len(ticker) <= 2 or ticker in AMBIGUOUS_NEWSAPI_TICKERS:
        subject_clause = company_clause
    else:
        subject_clause = f"({company_clause} OR {ticker})"
    return f"{subject_clause} AND (stock OR shares OR earnings OR revenue OR market)"


def normalize_newsapi_article(article: Mapping, ticker: str) -> dict | None:
    title = str(article.get("title") or "").strip()
    published_at = parse_datetime(article.get("publishedAt"))
    if not title or not published_at:
        return None
    source = article.get("source") or {}
    if isinstance(source, Mapping):
        source_name = source.get("name") or "NewsAPI"
    else:
        source_name = "NewsAPI"
    return {
        "title": title,
        "source": str(source_name),
        "published_at": _iso_z(published_at),
        "url": str(article.get("url") or ""),
        "tickers": [ticker],
        "category": "company",
        "replay_source": "newsapi_everything",
    }


def normalize_context_row(row: Mapping, *, default_source: str) -> dict | None:
    title = str(row.get("title") or row.get("headline") or "").strip()
    published_at = parse_datetime(
        row.get("published_at")
        or row.get("publishedAt")
        or row.get("timestamp")
        or row.get("date")
    )
    if not title or not published_at:
        return None
    tickers = row.get("tickers") or row.get("symbols") or []
    if isinstance(tickers, str):
        tickers = [tickers]
    return {
        "title": title,
        "source": str(row.get("source") or default_source),
        "published_at": _iso_z(published_at),
        "url": str(row.get("url") or row.get("link") or ""),
        "tickers": _normalize_tickers(tickers),
        "category": str(row.get("category") or row.get("source_type") or "").lower(),
        "replay_source": str(row.get("replay_source") or default_source),
        "synthetic": bool(row.get("synthetic", False)),
    }


def build_report(
    *,
    start: date,
    end: date,
    tickers: list[str],
    headlines: list[dict],
    source_reports: Mapping,
) -> dict:
    source_counts = Counter(row.get("source") or "unknown" for row in headlines)
    replay_source_counts = Counter(row.get("replay_source") or "unknown" for row in headlines)
    ticker_counts = Counter()
    for row in headlines:
        for ticker in row.get("tickers") or []:
            ticker_counts[ticker] += 1
    return {
        "generated_at": _iso_z(datetime.now(timezone.utc)),
        "window": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "ticker_count": len(tickers),
        "tickers": tickers,
        "headline_count": len(headlines),
        "source_counts": dict(sorted(source_counts.items())),
        "replay_source_counts": dict(sorted(replay_source_counts.items())),
        "ticker_context_counts": dict(sorted(ticker_counts.items())),
        "tickers_without_context": [
            ticker for ticker in tickers if ticker_counts.get(ticker, 0) == 0
        ],
        "source_reports": source_reports,
    }


def _sec_published_at(recent: Mapping, index: int) -> datetime | None:
    value = _list_value(recent, "acceptanceDateTime", index)
    parsed = parse_datetime(value)
    if parsed:
        return parsed
    filing_date = _list_value(recent, "filingDate", index)
    if not filing_date:
        return None
    try:
        return datetime.combine(date.fromisoformat(filing_date), dt_time(21, 0), tzinfo=timezone.utc)
    except ValueError:
        return None


def _sec_filing_url(cik: str, accession_no: str, primary_doc: str) -> str:
    if not accession_no:
        return f"https://data.sec.gov/submissions/CIK{cik}.json"
    accession_path = accession_no.replace("-", "")
    cik_path = str(int(cik))
    if not primary_doc:
        return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/{primary_doc}"


def _list_value(payload: Mapping, key: str, index: int) -> str:
    values = payload.get(key) or []
    if index >= len(values):
        return ""
    return str(values[index] or "").strip()


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if len(text) == 10:
            try:
                return datetime.combine(date.fromisoformat(text), dt_time(21, 0), tzinfo=timezone.utc)
            except ValueError:
                return None
        text = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    output = []
    seen = set()
    for ticker in tickers:
        value = str(ticker).upper().strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _dedupe_headlines(rows: Iterable[dict]) -> list[dict]:
    output = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("title") or "").lower().strip(),
            str(row.get("source") or "").lower().strip(),
            str(row.get("published_at") or "").strip(),
            tuple(row.get("tickers") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _dedupe_sources(rows: Iterable[dict]) -> list[dict]:
    output = []
    seen = set()
    for row in rows:
        key = (str(row.get("name") or "").lower(), str(row.get("url") or ""))
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return output


def write_json(path: str | Path, payload: Mapping) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
