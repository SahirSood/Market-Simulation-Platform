from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

from config import (
    RESEARCH_EMBED_BATCH_SIZE,
    RESEARCH_EMBED_LIMIT,
    RESEARCH_EXPAND_TRADABLE_UNIVERSE,
    RESEARCH_FORMS,
    RESEARCH_MAX_FILINGS_PER_TICKER,
    RESEARCH_MAX_TICKERS_PER_DAY,
    RESEARCH_TICKER_COOLDOWN_MINS,
    RESEARCH_TRIGGER_ACTIONS,
)
from liquidity import (
    SEED_LIQUIDITY_LEVELS,
    SEED_LIQUIDITY_ON_STARTUP,
    SEED_LIQUIDITY_QTY,
    SEED_LIQUIDITY_SPREAD_PCT,
)
from scripts.embed_worker import embed_once
from scripts.ingest_poller import poll_and_ingest_once

LOGGER = logging.getLogger(__name__)

_TICKER_RE = re.compile(r"(?<![A-Z0-9])\$?([A-Z][A-Z0-9.-]{0,5})(?![A-Z0-9])")
_COMMON_WORDS = {
    "A",
    "AI",
    "API",
    "CEO",
    "CFO",
    "ETF",
    "GDP",
    "IPO",
    "SEC",
    "USA",
    "USD",
}

COMPANY_ALIASES = {
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "TESLA": "TSLA",
    "AMAZON": "AMZN",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "NETFLIX": "NFLX",
    "INTEL": "INTC",
    "AMD": "AMD",
    "ADVANCED MICRO DEVICES": "AMD",
    "BROADCOM": "AVGO",
    "ORACLE": "ORCL",
    "SALESFORCE": "CRM",
    "ADOBE": "ADBE",
    "COSTCO": "COST",
    "WALMART": "WMT",
    "JPMORGAN": "JPM",
    "BANK OF AMERICA": "BAC",
    "TSMC": "TSM",
    "TAIWAN SEMICONDUCTOR": "TSM",
}


def extract_candidate_tickers(text: str, allowed_seed: Iterable[str] = ()) -> list[str]:
    source = str(text or "")
    found: list[str] = []
    seen: set[str] = set()
    seed = {symbol.upper() for symbol in allowed_seed}

    for alias, ticker in COMPANY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", source, flags=re.IGNORECASE):
            if ticker not in seen:
                seen.add(ticker)
                found.append(ticker)

    for match in _TICKER_RE.finditer(source):
        symbol = match.group(1).upper().strip(".-")
        if not symbol or symbol in _COMMON_WORDS:
            continue
        if symbol in seed or symbol in COMPANY_ALIASES.values() or match.group(0).startswith("$"):
            if symbol not in seen:
                seen.add(symbol)
                found.append(symbol)

    return found[:8]


@dataclass
class ResearchCoordinator:
    repository: object
    db_url: str
    embedding_service: object = None
    price_feed: object = None
    engine_adapter: object = None
    enabled: bool = True
    max_filings: int = RESEARCH_MAX_FILINGS_PER_TICKER
    forms: tuple[str, ...] = field(default_factory=lambda: tuple(RESEARCH_FORMS))
    max_per_day: int = RESEARCH_MAX_TICKERS_PER_DAY
    cooldown_mins: float = RESEARCH_TICKER_COOLDOWN_MINS
    embed_limit: int = RESEARCH_EMBED_LIMIT
    embed_batch_size: int = RESEARCH_EMBED_BATCH_SIZE
    expand_tradable_universe: bool = RESEARCH_EXPAND_TRADABLE_UNIVERSE

    def __post_init__(self):
        self._queue: deque[dict] = deque()
        self._queued: set[str] = set()
        self._last_requested_at: dict[str, float] = {}
        self._processed_count_by_day: dict[date, int] = {}
        self._events: deque[dict] = deque(maxlen=50)
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if not self.enabled or self._worker is not None:
            return
        self._worker = threading.Thread(target=self._run, name="research-coordinator", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)

    def request_from_decision(self, bot, decision) -> list[str]:
        if not self.enabled:
            return []

        action = str(getattr(decision, "action", "") or "").upper()
        trigger_actions = {value.upper() for value in RESEARCH_TRIGGER_ACTIONS}
        explicit = list(getattr(decision, "research_tickers", []) or [])
        candidates: list[str] = []

        if action in trigger_actions and getattr(decision, "ticker", None):
            candidates.append(str(decision.ticker))
        candidates.extend(explicit)

        context = getattr(bot, "_last_context", {}) or {}
        candidate_text = " ".join(
            str(value or "")
            for value in [
                getattr(decision, "headline_used", None),
                getattr(decision, "reasoning", None),
                *_headline_titles(context.get("trending_headlines", [])),
                *_headline_titles(context.get("recent_headlines", [])),
            ]
        )
        if explicit:
            candidates.extend(extract_candidate_tickers(candidate_text, _tradable(bot)))

        queued = []
        for ticker in candidates:
            if self.request_ticker(ticker, source_bot=getattr(bot, "bot_id", None), reason=action):
                queued.append(str(ticker).upper())
        return queued

    def request_ticker(self, ticker: str, source_bot: Optional[str] = None, reason: str = "manual") -> bool:
        symbol = str(ticker or "").upper().strip()
        if not self.enabled or not _valid_ticker(symbol):
            return False
        now = time.time()
        with self._lock:
            if self._budget_exhausted_locked():
                self._record_event_locked(symbol, "skipped_budget", source_bot, reason)
                return False
            if symbol in self._queued:
                return False
            last_at = self._last_requested_at.get(symbol, 0)
            if now - last_at < max(0.0, self.cooldown_mins) * 60:
                return False
            self._queued.add(symbol)
            self._last_requested_at[symbol] = now
            self._queue.append({"ticker": symbol, "source_bot": source_bot, "reason": reason})
            self._record_event_locked(symbol, "queued", source_bot, reason)
            return True

    def status(self) -> dict:
        with self._lock:
            today = date.today()
            return {
                "enabled": self.enabled,
                "queued_count": len(self._queue),
                "queued_tickers": [row["ticker"] for row in list(self._queue)[:20]],
                "processed_today": self._processed_count_by_day.get(today, 0),
                "max_per_day": self.max_per_day,
                "cooldown_mins": self.cooldown_mins,
                "recent_events": list(self._events),
            }

    def _run(self) -> None:
        while not self._stop_event.is_set():
            item = None
            with self._lock:
                if self._queue:
                    item = self._queue.popleft()
                    self._queued.discard(item["ticker"])
            if item is None:
                self._stop_event.wait(2.0)
                continue
            self._process_item(item)

    def _process_item(self, item: dict) -> None:
        ticker = item["ticker"]
        source_bot = item.get("source_bot")
        reason = item.get("reason", "unknown")
        try:
            existing = _count_docs(self.repository, ticker)
            if existing > 0:
                self._maybe_add_tradable(ticker)
                with self._lock:
                    self._record_event_locked(ticker, "already_covered", source_bot, reason, {"documents": existing})
                return

            result = poll_and_ingest_once(
                tickers=[ticker],
                db_url=self.db_url,
                max_filings=self.max_filings,
                forms=list(self.forms),
                repository=self.repository,
                ingestion_service=None,
                max_retries=1,
            )
            embedded = embed_once(
                db_url=self.db_url,
                limit=self.embed_limit,
                batch_size=self.embed_batch_size,
                repository=self.repository,
                embedding_service=self.embedding_service,
                max_retries=1,
            )
            updated = result.get("updated_tickers", [])
            status = "ingested" if ticker in updated else "no_new_filings"
            if ticker in updated:
                self._maybe_add_tradable(ticker)
                self._increment_processed()
            with self._lock:
                self._record_event_locked(
                    ticker,
                    status,
                    source_bot,
                    reason,
                    {
                        "updated_tickers": updated,
                        "unknown_tickers": result.get("unknown_tickers", []),
                        "embedded": embedded,
                    },
                )
        except Exception as exc:
            LOGGER.warning("Research ingestion failed for %s: %s", ticker, exc)
            with self._lock:
                self._record_event_locked(ticker, "failed", source_bot, reason, {"error": str(exc)[:300]})

    def _maybe_add_tradable(self, ticker: str) -> None:
        if not self.expand_tradable_universe or self.price_feed is None:
            return
        try:
            price = float(self.price_feed.get_price(ticker))
            add = getattr(self.price_feed, "add_tradable_ticker", None)
            if callable(add):
                add(ticker)
            if SEED_LIQUIDITY_ON_STARTUP and self.engine_adapter is not None:
                self.engine_adapter.seed_liquidity(
                    ticker=ticker,
                    mid_price=price,
                    levels=SEED_LIQUIDITY_LEVELS,
                    quantity=SEED_LIQUIDITY_QTY,
                    spread_pct=SEED_LIQUIDITY_SPREAD_PCT,
                )
        except Exception as exc:
            LOGGER.warning("Could not add researched ticker %s to tradable universe: %s", ticker, exc)

    def _increment_processed(self) -> None:
        with self._lock:
            today = date.today()
            self._processed_count_by_day[today] = self._processed_count_by_day.get(today, 0) + 1

    def _budget_exhausted_locked(self) -> bool:
        if self.max_per_day <= 0:
            return False
        today = date.today()
        return self._processed_count_by_day.get(today, 0) >= self.max_per_day

    def _record_event_locked(
        self,
        ticker: str,
        status: str,
        source_bot: Optional[str],
        reason: str,
        metadata: Optional[dict] = None,
    ) -> None:
        self._events.appendleft(
            {
                "ticker": ticker,
                "status": status,
                "source_bot": source_bot,
                "reason": reason,
                "metadata": metadata or {},
                "timestamp": time.time(),
            }
        )


def _headline_titles(rows) -> list[str]:
    return [str(row.get("title") or "") for row in rows or [] if isinstance(row, dict)]


def _tradable(bot) -> list[str]:
    get_tradable = getattr(getattr(bot, "price_feed", None), "get_tradable_tickers", None)
    if callable(get_tradable):
        return get_tradable()
    return []


def _count_docs(repository, ticker: str) -> int:
    counter = getattr(repository, "count_documents_by_ticker", None)
    if callable(counter):
        return int(counter(ticker))
    return 0


def _valid_ticker(symbol: str) -> bool:
    return bool(symbol) and len(symbol) <= 6 and symbol.replace(".", "").replace("-", "").isalnum()
