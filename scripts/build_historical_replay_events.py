"""Build replay-compatible historical event files.

The builder is intentionally conservative: daily price data can come from
yfinance or a local JSON export, historical headlines can be imported from a
local timestamped file, and synthetic market summaries are clearly labeled when
used as fallback context.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import TRADABLE_TICKERS  # noqa: E402


DEFAULT_BENCHMARKS = ("SPY", "QQQ", "TLT", "GLD")
NEWS_MODES = {"historical-first", "news-file", "synthetic", "price-only"}


@dataclass(frozen=True)
class PriceRow:
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build daily historical replay events with auditable context."
    )
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=list(TRADABLE_TICKERS),
        help="Ticker universe for event prices and ticker-specific context.",
    )
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        default=list(DEFAULT_BENCHMARKS),
        help="Benchmark tickers to include in benchmark fields.",
    )
    parser.add_argument(
        "--frequency",
        default="1d",
        choices=["1d"],
        help="Event frequency. Only daily close events are currently supported.",
    )
    parser.add_argument(
        "--event-time-utc",
        default="21:00:00Z",
        help="UTC time used for each daily event timestamp.",
    )
    parser.add_argument(
        "--price-file",
        default=None,
        help="Optional local JSON price export. If omitted, yfinance is used.",
    )
    parser.add_argument(
        "--news-mode",
        default="historical-first",
        choices=sorted(NEWS_MODES),
        help=(
            "historical-first uses timestamped news when available and synthetic "
            "fallback; news-file uses only --news-file; synthetic uses only "
            "price-derived summaries; price-only emits no headlines."
        ),
    )
    parser.add_argument(
        "--news-file",
        default=None,
        help="Optional local JSON/JSONL historical headline export.",
    )
    parser.add_argument(
        "--news-lookback-hours",
        type=int,
        default=24,
        help="Maximum headline age allowed at each replay timestamp.",
    )
    parser.add_argument(
        "--min-headlines-per-event",
        type=int,
        default=2,
        help="Minimum context count before a non-price-only event is flagged.",
    )
    parser.add_argument("--output", required=True, help="Replay event JSON output path.")
    parser.add_argument(
        "--report",
        default=None,
        help="Quality report JSON path. Defaults to <output>.report.json.",
    )
    return parser.parse_args()


def load_price_file(path: str | Path) -> dict[str, list[PriceRow]]:
    """Load a local price JSON file into normalized per-ticker rows."""
    payload = _read_json_or_jsonl(Path(path))
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        return _price_history_from_replay_events(payload["events"])
    if isinstance(payload, dict) and "prices" in payload:
        payload = payload["prices"]

    rows_by_ticker: dict[str, list[dict]] = {}
    if isinstance(payload, dict):
        for ticker, rows in payload.items():
            rows_by_ticker[str(ticker).upper().strip()] = list(rows or [])
    elif isinstance(payload, list):
        for row in payload:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
            if not ticker:
                continue
            rows_by_ticker.setdefault(ticker, []).append(row)
    else:
        raise ValueError("Price file must be a JSON object or list")

    return _normalize_price_history(rows_by_ticker)


def _price_history_from_replay_events(events: Sequence[Mapping]) -> dict[str, list[PriceRow]]:
    rows_by_ticker: dict[str, list[dict]] = {}
    for event in events or []:
        if not isinstance(event, Mapping):
            continue
        raw_time = event.get("timestamp") or event.get("as_of_time")
        prices = event.get("prices") or {}
        ohlcv = event.get("ohlcv") or {}
        if not raw_time or not isinstance(prices, Mapping):
            continue
        for ticker, price in prices.items():
            symbol = str(ticker).upper().strip()
            if not symbol:
                continue
            row = dict(ohlcv.get(symbol) or ohlcv.get(ticker) or {})
            row.setdefault("date", raw_time)
            row.setdefault("close", row.get("price", price))
            row.setdefault("open", row.get("close", price))
            row.setdefault("high", row.get("close", price))
            row.setdefault("low", row.get("close", price))
            rows_by_ticker.setdefault(symbol, []).append(row)
    return _normalize_price_history(rows_by_ticker)


def load_news_file(path: str | Path, known_tickers: Sequence[str]) -> list[dict]:
    """Load timestamped historical headlines from JSON or JSONL."""
    payload = _read_json_or_jsonl(Path(path))
    if isinstance(payload, dict):
        for key in ("headlines", "articles", "events"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("News file must be a JSON list or object with headlines/articles/events")

    normalized = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        item = _normalize_news_item(row, known_tickers)
        if item is not None:
            normalized.append(item)
    normalized.sort(key=lambda item: item["published_at"])
    return normalized


def fetch_yfinance_history(
    tickers: Sequence[str],
    start: date,
    end: date,
) -> dict[str, list[PriceRow]]:
    """Fetch daily OHLCV rows from yfinance."""
    import yfinance as yf

    symbols = _normalize_tickers(tickers)
    frame = yf.download(
        symbols,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=False,
    )
    history = _price_history_from_yfinance(frame, symbols)
    if not any(history.values()):
        raise RuntimeError("No historical price rows returned by yfinance")
    return history


def build_historical_replay_payload(
    *,
    price_history: Mapping[str, Sequence[PriceRow | Mapping]],
    start: date,
    end: date,
    tickers: Sequence[str],
    benchmarks: Sequence[str],
    frequency: str = "1d",
    event_time_utc: str = "21:00:00Z",
    news_mode: str = "historical-first",
    news_items: Sequence[dict] | None = None,
    news_lookback_hours: int = 24,
    min_headlines_per_event: int = 2,
    source_provider: str = "price_file",
    generated_at: datetime | None = None,
) -> tuple[dict, dict]:
    if frequency != "1d":
        raise ValueError("Only 1d frequency is currently supported")
    if news_mode not in NEWS_MODES:
        raise ValueError(f"Unknown news mode: {news_mode}")

    tickers = _normalize_tickers(tickers)
    benchmarks = _normalize_tickers(benchmarks)
    all_symbols = _normalize_tickers([*tickers, *benchmarks])
    min_headlines = max(0, int(min_headlines_per_event or 0))
    generated_at = generated_at or datetime.now(timezone.utc)

    history = _normalize_price_history(price_history)
    row_by_date = {
        ticker: {row.date: row for row in rows}
        for ticker, rows in history.items()
    }
    feature_history = _compute_feature_history(history)
    event_dates = _event_dates(history, all_symbols, start, end)

    events = []
    missing_prices: dict[str, int] = {symbol: 0 for symbol in all_symbols}
    dropped_rows = []

    for event_date in event_dates:
        event_time = _event_datetime(event_date, event_time_utc)
        prices = {}
        ohlcv = {}
        generated_features = {}

        for symbol in all_symbols:
            row = row_by_date.get(symbol, {}).get(event_date)
            if row is None:
                missing_prices[symbol] = missing_prices.get(symbol, 0) + 1
                continue
            prices[symbol] = _round(row.close, 4)
            ohlcv[symbol] = {
                "open": _round(row.open, 4),
                "high": _round(row.high, 4),
                "low": _round(row.low, 4),
                "close": _round(row.close, 4),
                "volume": int(row.volume or 0),
            }
            generated_features[symbol] = feature_history.get(symbol, {}).get(
                event_date,
                {},
            )

        if not prices:
            dropped_rows.append({"date": event_date.isoformat(), "reason": "no prices"})
            continue

        benchmark_prices = {
            symbol: prices[symbol]
            for symbol in benchmarks
            if symbol in prices
        }
        benchmark_returns = {
            symbol: generated_features.get(symbol, {}).get("return_1d")
            for symbol in benchmarks
            if symbol in generated_features
        }
        market_regime = _market_regime(
            event_date,
            generated_features,
            tickers,
        )
        context = _build_news_context(
            news_mode=news_mode,
            event_time=event_time,
            tickers=tickers,
            prices=prices,
            generated_features=generated_features,
            market_regime=market_regime,
            news_items=list(news_items or []),
            news_lookback_hours=max(0, int(news_lookback_hours or 0)),
            min_headlines_per_event=min_headlines,
        )

        expected_notes = []
        if news_mode == "price-only":
            expected_notes.append(
                "Price-only smoke-test event; do not use for ML-grade replay conclusions."
            )
        elif context["news_coverage"]["real_headline_count"] == 0:
            expected_notes.append(
                "Synthetic replay context only; replace with timestamped historical news before ML-grade replay."
            )

        events.append({
            "timestamp": _iso_z(event_time),
            "prices": prices,
            "ohlcv": ohlcv,
            "benchmark_prices": benchmark_prices,
            "benchmark_returns": benchmark_returns,
            "market_regime": market_regime,
            "generated_features": generated_features,
            "trending_headlines": context["trending_headlines"],
            "recent_headlines": context["recent_headlines"],
            "ticker_headlines": context["ticker_headlines"],
            "source_events": context["source_events"],
            "news_coverage": context["news_coverage"],
            "expected_notes": expected_notes,
        })

    report = build_quality_report(
        events=events,
        tickers=tickers,
        benchmarks=benchmarks,
        start=start,
        end=end,
        source_provider=source_provider,
        news_mode=news_mode,
        min_headlines_per_event=min_headlines,
        missing_prices=missing_prices,
        dropped_rows=dropped_rows,
    )
    dataset_grade = report["dataset_grade"]
    config = {
        "source": "historical_event_builder",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "frequency": frequency,
        "event_time_utc": event_time_utc,
        "tickers": tickers,
        "benchmarks": benchmarks,
        "news_mode": news_mode,
        "news_sources": report["news_sources"],
        "news_lookback_hours": news_lookback_hours,
        "min_headlines_per_event": min_headlines,
        "synthetic_headline_policy": _synthetic_policy(news_mode),
        "generated_at": _iso_z(generated_at),
        "data_provider": source_provider,
        "dataset_grade": dataset_grade,
        "no_lookahead_policy": (
            "Selected headline published_at values must be at or before each "
            "event timestamp; generated features use OHLCV rows through the "
            "event date only."
        ),
        "event_count": len(events),
        "trading_day_count": len(events),
        "missing_data_summary": report["missing_data_summary"],
        "news_coverage_summary": report["news_coverage_summary"],
    }
    payload = {
        "name": f"Historical Daily Replay {start.isoformat()} to {end.isoformat()}",
        "description": _payload_description(dataset_grade, start, end),
        "config": config,
        "events": events,
    }
    report["output_summary"] = {
        "name": payload["name"],
        "description": payload["description"],
        "dataset_grade": dataset_grade,
    }
    return payload, report


def build_quality_report(
    *,
    events: Sequence[dict],
    tickers: Sequence[str],
    benchmarks: Sequence[str],
    start: date,
    end: date,
    source_provider: str,
    news_mode: str,
    min_headlines_per_event: int,
    missing_prices: Mapping[str, int] | None = None,
    dropped_rows: Sequence[dict] | None = None,
) -> dict:
    timestamps = [event.get("timestamp") or event.get("as_of_time") for event in events]
    timestamp_counts = {}
    for value in timestamps:
        timestamp_counts[value] = timestamp_counts.get(value, 0) + 1
    duplicate_timestamps = [
        value for value, count in timestamp_counts.items() if value and count > 1
    ]

    total_headlines = 0
    real_headlines = 0
    synthetic_headlines = 0
    events_below_min = []
    news_sources = set()
    no_lookahead_violations = []
    earliest = timestamps[0] if timestamps else None
    latest = timestamps[-1] if timestamps else None

    for index, event in enumerate(events):
        event_time = _parse_datetime(event.get("timestamp") or event.get("as_of_time"))
        headline_rows = list(_iter_event_headlines(event))
        headline_count = len(headline_rows)
        total_headlines += headline_count
        if headline_count < min_headlines_per_event and news_mode != "price-only":
            events_below_min.append({
                "event_index": index,
                "timestamp": event.get("timestamp"),
                "headline_count": headline_count,
            })
        for headline in headline_rows:
            if headline.get("synthetic"):
                synthetic_headlines += 1
            else:
                real_headlines += 1
            if headline.get("source"):
                news_sources.add(str(headline["source"]))
            published_at = _parse_datetime(headline.get("published_at"))
            if published_at and event_time and published_at > event_time:
                no_lookahead_violations.append({
                    "event_index": index,
                    "timestamp": event.get("timestamp"),
                    "title": headline.get("title"),
                    "published_at": headline.get("published_at"),
                })

    missing_prices = dict(missing_prices or {})
    report = {
        "generated_at": _iso_z(datetime.now(timezone.utc)),
        "source_provider": source_provider,
        "news_mode": news_mode,
        "window": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "earliest_timestamp": earliest,
            "latest_timestamp": latest,
        },
        "event_count": len(events),
        "ticker_count": len(tickers),
        "benchmark_count": len(benchmarks),
        "tickers": list(tickers),
        "benchmarks": list(benchmarks),
        "total_headline_count": total_headlines,
        "real_headline_count": real_headlines,
        "synthetic_headline_count": synthetic_headlines,
        "events_below_min_headline_coverage": len(events_below_min),
        "events_below_min_headline_coverage_detail": events_below_min[:50],
        "news_sources": sorted(news_sources),
        "missing_price_count": sum(int(value or 0) for value in missing_prices.values()),
        "missing_data_summary": {
            "missing_prices_by_symbol": missing_prices,
            "symbols_with_missing_prices": sorted(
                symbol for symbol, count in missing_prices.items() if count
            ),
        },
        "duplicate_timestamp_count": len(duplicate_timestamps),
        "duplicate_timestamps": duplicate_timestamps,
        "dropped_rows": list(dropped_rows or []),
        "dropped_row_count": len(dropped_rows or []),
        "no_lookahead_violation_count": len(no_lookahead_violations),
        "no_lookahead_violations": no_lookahead_violations[:50],
        "news_coverage_summary": {
            "total_headline_count": total_headlines,
            "real_headline_count": real_headlines,
            "synthetic_headline_count": synthetic_headlines,
            "events_below_min_headline_coverage": len(events_below_min),
            "min_headlines_per_event": min_headlines_per_event,
        },
    }
    report["dataset_grade"] = _dataset_grade(report)
    return report


def write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if end < start:
        raise ValueError("--end must be on or after --start")

    tickers = _normalize_tickers(args.tickers)
    benchmarks = _normalize_tickers(args.benchmarks)
    all_symbols = _normalize_tickers([*tickers, *benchmarks])

    if args.price_file:
        price_history = load_price_file(args.price_file)
        source_provider = "price_file"
    else:
        price_history = fetch_yfinance_history(all_symbols, start, end)
        source_provider = "yfinance"

    news_items = []
    if args.news_file:
        news_items = load_news_file(args.news_file, all_symbols)

    payload, report = build_historical_replay_payload(
        price_history=price_history,
        start=start,
        end=end,
        tickers=tickers,
        benchmarks=benchmarks,
        frequency=args.frequency,
        event_time_utc=args.event_time_utc,
        news_mode=args.news_mode,
        news_items=news_items,
        news_lookback_hours=args.news_lookback_hours,
        min_headlines_per_event=args.min_headlines_per_event,
        source_provider=source_provider,
    )

    output_path = Path(args.output)
    report_path = Path(args.report) if args.report else output_path.with_suffix(".report.json")
    write_json(output_path, payload)
    write_json(report_path, report)
    print(json.dumps({
        "output": str(output_path),
        "report": str(report_path),
        "event_count": report["event_count"],
        "dataset_grade": report["dataset_grade"],
        "real_headline_count": report["real_headline_count"],
        "synthetic_headline_count": report["synthetic_headline_count"],
        "no_lookahead_violation_count": report["no_lookahead_violation_count"],
    }, indent=2))
    return 0


def _read_json_or_jsonl(path: Path):
    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_price_history(
    price_history: Mapping[str, Sequence[PriceRow | Mapping]],
) -> dict[str, list[PriceRow]]:
    normalized: dict[str, list[PriceRow]] = {}
    for ticker, rows in (price_history or {}).items():
        symbol = str(ticker).upper().strip()
        if not symbol:
            continue
        parsed_rows = []
        for row in rows or []:
            parsed = row if isinstance(row, PriceRow) else _price_row_from_mapping(symbol, row)
            if parsed is not None:
                parsed_rows.append(parsed)
        deduped = {row.date: row for row in parsed_rows}
        normalized[symbol] = [deduped[day] for day in sorted(deduped)]
    return normalized


def _price_row_from_mapping(symbol: str, row: Mapping) -> PriceRow | None:
    raw_date = row.get("date") or row.get("timestamp") or row.get("as_of_time")
    close = _coerce_float(row.get("close") or row.get("Close") or row.get("price"))
    if raw_date is None or close is None:
        return None
    open_price = _coerce_float(row.get("open") or row.get("Open")) or close
    high = _coerce_float(row.get("high") or row.get("High")) or max(open_price, close)
    low = _coerce_float(row.get("low") or row.get("Low")) or min(open_price, close)
    volume = _coerce_int(row.get("volume") or row.get("Volume"))
    return PriceRow(
        ticker=symbol,
        date=_parse_date(raw_date),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _price_history_from_yfinance(frame, symbols: Sequence[str]) -> dict[str, list[PriceRow]]:
    history: dict[str, list[PriceRow]] = {symbol: [] for symbol in symbols}
    if frame is None or getattr(frame, "empty", True):
        return history

    multi_index = getattr(getattr(frame, "columns", None), "nlevels", 1) > 1
    for symbol in symbols:
        try:
            ticker_frame = frame[symbol] if multi_index else frame
        except Exception:
            continue
        rows = []
        for index, row in ticker_frame.iterrows():
            close = _series_value(row, "Close", "close", "Adj Close", "adj_close")
            if close is None:
                continue
            open_price = _series_value(row, "Open", "open") or close
            high = _series_value(row, "High", "high") or max(open_price, close)
            low = _series_value(row, "Low", "low") or min(open_price, close)
            volume = _coerce_int(_series_value(row, "Volume", "volume"))
            rows.append(PriceRow(
                ticker=symbol,
                date=_parse_date(index),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            ))
        history[symbol] = rows
    return _normalize_price_history(history)


def _compute_feature_history(
    history: Mapping[str, Sequence[PriceRow]],
) -> dict[str, dict[date, dict]]:
    features: dict[str, dict[date, dict]] = {}
    for symbol, rows in history.items():
        ordered = sorted(rows, key=lambda row: row.date)
        daily_returns: list[float | None] = []
        symbol_features = {}
        for index, row in enumerate(ordered):
            prev = ordered[index - 1] if index > 0 else None
            return_1d = _return(row.close, prev.close) if prev else None
            daily_returns.append(return_1d)
            closes_20 = [item.close for item in ordered[max(0, index - 19): index + 1]]
            prior_volumes = [
                item.volume
                for item in ordered[max(0, index - 20): index]
                if item.volume is not None and item.volume > 0
            ]
            recent_returns = [
                value
                for value in daily_returns[max(0, index - 19): index + 1]
                if value is not None
            ]
            avg_volume = mean(prior_volumes) if prior_volumes else None
            ma20 = mean(closes_20) if closes_20 else None
            symbol_features[row.date] = {
                "return_1d": _round(return_1d),
                "return_5d": _round(_return(row.close, ordered[index - 5].close) if index >= 5 else None),
                "return_20d": _round(_return(row.close, ordered[index - 20].close) if index >= 20 else None),
                "rolling_volatility_20d": _round(stdev(recent_returns) if len(recent_returns) >= 2 else None),
                "volume_ratio_20d": _round((row.volume / avg_volume) if row.volume and avg_volume else None),
                "gap_from_previous_close": _round(_return(row.open, prev.close) if prev else None),
                "distance_from_20d_ma": _round(_return(row.close, ma20) if ma20 else None),
            }
        features[symbol] = symbol_features
    return features


def _event_dates(
    history: Mapping[str, Sequence[PriceRow]],
    symbols: Sequence[str],
    start: date,
    end: date,
) -> list[date]:
    dates = set()
    for symbol in symbols:
        for row in history.get(symbol, []) or []:
            if start <= row.date <= end:
                dates.add(row.date)
    return sorted(dates)


def _build_news_context(
    *,
    news_mode: str,
    event_time: datetime,
    tickers: Sequence[str],
    prices: Mapping[str, float],
    generated_features: Mapping[str, dict],
    market_regime: Mapping[str, object],
    news_items: Sequence[dict],
    news_lookback_hours: int,
    min_headlines_per_event: int,
) -> dict:
    ticker_headlines: dict[str, list[dict]] = {ticker: [] for ticker in tickers if ticker in prices}
    trending: list[dict] = []
    recent: list[dict] = []

    if news_mode in {"historical-first", "news-file"}:
        selected = _select_real_headlines(
            news_items,
            event_time=event_time,
            tickers=tickers,
            lookback_hours=news_lookback_hours,
        )
        trending.extend(selected["trending_headlines"])
        recent.extend(selected["recent_headlines"])
        for ticker, rows in selected["ticker_headlines"].items():
            ticker_headlines.setdefault(ticker, []).extend(rows)

    total_context = _headline_count(trending, recent, ticker_headlines)
    if news_mode == "synthetic" or (
        news_mode == "historical-first" and total_context < min_headlines_per_event
    ):
        synthetic = _synthetic_news_context(
            event_time=event_time,
            tickers=tickers,
            prices=prices,
            generated_features=generated_features,
            market_regime=market_regime,
        )
        trending.extend(synthetic["trending_headlines"])
        recent.extend(synthetic["recent_headlines"])
        for ticker, rows in synthetic["ticker_headlines"].items():
            ticker_headlines.setdefault(ticker, []).extend(rows)

    if news_mode == "price-only":
        trending = []
        recent = []
        ticker_headlines = {ticker: [] for ticker in tickers if ticker in prices}

    ticker_headlines = {
        ticker: _dedupe_headline_dicts(rows)[:2]
        for ticker, rows in ticker_headlines.items()
        if rows
    }
    trending = _dedupe_headline_dicts(trending)[:6]
    recent = _dedupe_headline_dicts(recent)[:6]
    source_events = _source_events(trending, recent, ticker_headlines)
    real_count = sum(1 for row in source_events if not row.get("synthetic"))
    synthetic_count = sum(1 for row in source_events if row.get("synthetic"))
    total = len(source_events)

    return {
        "trending_headlines": trending,
        "recent_headlines": recent,
        "ticker_headlines": ticker_headlines,
        "source_events": source_events,
        "news_coverage": {
            "headline_count": total,
            "real_headline_count": real_count,
            "synthetic_headline_count": synthetic_count,
            "has_real_news": real_count > 0,
            "has_synthetic_market_summary": synthetic_count > 0,
            "below_min_headlines": (
                total < min_headlines_per_event
                if news_mode != "price-only"
                else False
            ),
            "min_headlines_required": min_headlines_per_event,
            "news_mode": news_mode,
            "sources": sorted({row.get("source") for row in source_events if row.get("source")}),
            "no_lookahead_violation_count": _selected_no_lookahead_violations(
                source_events,
                event_time,
            ),
        },
    }


def _select_real_headlines(
    news_items: Sequence[dict],
    *,
    event_time: datetime,
    tickers: Sequence[str],
    lookback_hours: int,
) -> dict:
    earliest = event_time - timedelta(hours=lookback_hours)
    eligible = [
        item
        for item in news_items
        if earliest <= item["published_at"] <= event_time
    ]
    eligible.sort(key=lambda item: item["published_at"], reverse=True)
    ticker_set = set(tickers)
    broad = [
        item for item in eligible
        if not item.get("tickers") or str(item.get("category") or "").lower() in {"market", "macro", "economy"}
    ]
    if not broad:
        broad = eligible

    ticker_headlines: dict[str, list[dict]] = {}
    for ticker in ticker_set:
        rows = [
            _headline_from_news_item(item, event_time)
            for item in eligible
            if ticker in set(item.get("tickers") or [])
        ]
        if rows:
            ticker_headlines[ticker] = rows[:2]

    return {
        "trending_headlines": [
            _headline_from_news_item(item, event_time)
            for item in broad[:6]
        ],
        "recent_headlines": [
            _headline_from_news_item(item, event_time)
            for item in eligible[:6]
        ],
        "ticker_headlines": ticker_headlines,
    }


def _synthetic_news_context(
    *,
    event_time: datetime,
    tickers: Sequence[str],
    prices: Mapping[str, float],
    generated_features: Mapping[str, dict],
    market_regime: Mapping[str, object],
) -> dict:
    synthetic = []
    spy_return = generated_features.get("SPY", {}).get("return_1d")
    qqq_return = generated_features.get("QQQ", {}).get("return_1d")
    tlt_return = generated_features.get("TLT", {}).get("return_1d")
    if spy_return is not None or qqq_return is not None or tlt_return is not None:
        synthetic.append(_synthetic_headline(
            (
                f"SPY closed {_direction_phrase(spy_return)} while QQQ closed "
                f"{_direction_phrase(qqq_return)} and TLT closed {_direction_phrase(tlt_return)}, "
                f"indicating {market_regime.get('risk_regime', 'neutral')} replay conditions"
            ),
            event_time,
        ))
    else:
        synthetic.append(_synthetic_headline(
            f"Replay market snapshot recorded close prices for {len(prices)} instruments",
            event_time,
        ))

    up_count = sum(
        1
        for features in generated_features.values()
        if features.get("return_1d") is not None and features.get("return_1d") > 0
    )
    return_count = sum(
        1
        for features in generated_features.values()
        if features.get("return_1d") is not None
    )
    if return_count:
        synthetic.append(_synthetic_headline(
            f"{up_count} of {return_count} tracked instruments closed higher in the replay universe",
            event_time,
        ))

    movers = sorted(
        (
            (ticker, generated_features.get(ticker, {}).get("return_1d"))
            for ticker in tickers
            if ticker in prices and generated_features.get(ticker, {}).get("return_1d") is not None
        ),
        key=lambda item: abs(item[1] or 0),
        reverse=True,
    )
    if movers:
        move_text = ", ".join(
            f"{ticker} {_direction_phrase(value)}"
            for ticker, value in movers[:4]
        )
        synthetic.append(_synthetic_headline(
            f"Top replay movers by close: {move_text}",
            event_time,
        ))

    ticker_headlines = {}
    for ticker in tickers:
        if ticker not in prices:
            continue
        features = generated_features.get(ticker, {})
        volume_ratio = features.get("volume_ratio_20d")
        volume_text = ""
        if volume_ratio is not None:
            if volume_ratio >= 1.2:
                volume_text = " with volume above its recent average"
            elif volume_ratio <= 0.8:
                volume_text = " with volume below its recent average"
            else:
                volume_text = " with volume near its recent average"
        trend_text = ""
        distance = features.get("distance_from_20d_ma")
        if distance is not None:
            trend_text = f" and traded {_direction_from_zero(distance)} its 20-day average"
        ticker_headlines[ticker] = [
            _synthetic_headline(
                f"{ticker} closed {_direction_phrase(features.get('return_1d'))} at ${prices[ticker]:,.2f}{volume_text}{trend_text}",
                event_time,
            )
        ]

    return {
        "trending_headlines": synthetic[:2],
        "recent_headlines": synthetic[2:4],
        "ticker_headlines": ticker_headlines,
    }


def _market_regime(
    event_date: date,
    generated_features: Mapping[str, dict],
    tickers: Sequence[str],
) -> dict:
    spy = generated_features.get("SPY", {})
    qqq = generated_features.get("QQQ", {})
    tlt = generated_features.get("TLT", {})
    gld = generated_features.get("GLD", {})
    spy_return = spy.get("return_1d")
    qqq_return = qqq.get("return_1d")
    tlt_return = tlt.get("return_1d")
    spy_trend = spy.get("return_20d")
    spy_vol = spy.get("rolling_volatility_20d")

    if spy_return is not None and spy_return <= -0.005 and (tlt_return or 0) >= 0:
        risk_regime = "risk_off"
    elif spy_return is not None and spy_return >= 0.005 and (qqq_return or 0) >= 0:
        risk_regime = "risk_on"
    else:
        risk_regime = "neutral"

    if spy_trend is None:
        trend_regime = "unknown"
    elif spy_trend >= 0.02:
        trend_regime = "up"
    elif spy_trend <= -0.02:
        trend_regime = "down"
    else:
        trend_regime = "sideways"

    if spy_vol is None:
        volatility_regime = "unknown"
    elif spy_vol >= 0.02:
        volatility_regime = "high"
    elif spy_vol >= 0.01:
        volatility_regime = "medium"
    else:
        volatility_regime = "low"

    breadth_returns = [
        generated_features.get(ticker, {}).get("return_1d")
        for ticker in tickers
        if generated_features.get(ticker, {}).get("return_1d") is not None
    ]
    breadth_proxy = (
        sum(1 for value in breadth_returns if value > 0) / len(breadth_returns)
        if breadth_returns
        else None
    )

    return {
        "date": event_date.isoformat(),
        "spy_return_1d": _round(spy_return),
        "qqq_return_1d": _round(qqq_return),
        "tlt_return_1d": _round(tlt_return),
        "gld_return_1d": _round(gld.get("return_1d")),
        "risk_regime": risk_regime,
        "trend_regime": trend_regime,
        "volatility_regime": volatility_regime,
        "breadth_proxy": _round(breadth_proxy),
    }


def _normalize_news_item(row: Mapping, known_tickers: Sequence[str]) -> dict | None:
    title = str(row.get("title") or row.get("headline") or row.get("name") or "").strip()
    raw_time = (
        row.get("published_at")
        or row.get("publishedAt")
        or row.get("timestamp")
        or row.get("date")
    )
    if not title or raw_time is None:
        return None
    published_at = _parse_datetime(raw_time)
    if published_at is None:
        return None

    source = row.get("source") or row.get("source_name") or "historical_news_file"
    if isinstance(source, dict):
        source = source.get("name") or source.get("id") or "historical_news_file"
    tickers = row.get("tickers") or row.get("symbols") or row.get("ticker") or row.get("symbol") or []
    if isinstance(tickers, str):
        tickers = [tickers]
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        normalized_tickers = _extract_known_tickers(title, known_tickers)

    return {
        "title": title,
        "source": str(source),
        "published_at": published_at,
        "url": str(row.get("url") or ""),
        "tickers": normalized_tickers,
        "category": str(row.get("category") or row.get("source_type") or "").lower(),
        "replay_source": str(row.get("replay_source") or "historical_news_file"),
        "synthetic": bool(row.get("synthetic", False)),
    }


def _headline_from_news_item(item: Mapping, event_time: datetime) -> dict:
    published_at = item["published_at"]
    age_minutes = max(0, int((event_time - published_at).total_seconds() // 60))
    return {
        "title": item["title"],
        "source": item.get("source") or "historical_news_file",
        "published_at": _iso_z(published_at),
        "url": item.get("url") or "",
        "age_minutes": age_minutes,
        "age_label": _age_label(age_minutes),
        "replay_source": item.get("replay_source") or "historical_news_file",
        "synthetic": bool(item.get("synthetic", False)),
    }


def _synthetic_headline(title: str, event_time: datetime) -> dict:
    return {
        "title": title,
        "source": "generated_market_summary",
        "published_at": _iso_z(event_time),
        "url": "",
        "age_minutes": 0,
        "age_label": "replay",
        "replay_source": "derived_from_ohlcv",
        "synthetic": True,
    }


def _source_events(
    trending: Sequence[dict],
    recent: Sequence[dict],
    ticker_headlines: Mapping[str, Sequence[dict]],
) -> list[dict]:
    rows = []
    for section, headlines in (
        ("trending_headlines", trending),
        ("recent_headlines", recent),
    ):
        for headline in headlines:
            rows.append(_source_event_row(headline, section))
    for ticker, headlines in ticker_headlines.items():
        for headline in headlines:
            rows.append(_source_event_row(headline, "ticker_headlines", ticker=ticker))
    return _dedupe_source_events(rows)


def _source_event_row(headline: Mapping, section: str, ticker: str | None = None) -> dict:
    return {
        "title": headline.get("title"),
        "source": headline.get("source"),
        "published_at": headline.get("published_at"),
        "url": headline.get("url") or "",
        "replay_source": headline.get("replay_source"),
        "synthetic": bool(headline.get("synthetic", False)),
        "section": section,
        "ticker": ticker,
    }


def _iter_event_headlines(event: Mapping) -> Iterable[dict]:
    for key in ("trending_headlines", "recent_headlines"):
        for row in event.get(key) or []:
            if isinstance(row, dict):
                yield row
    for rows in (event.get("ticker_headlines") or {}).values():
        for row in rows or []:
            if isinstance(row, dict):
                yield row


def _selected_no_lookahead_violations(rows: Sequence[Mapping], event_time: datetime) -> int:
    count = 0
    for row in rows:
        published_at = _parse_datetime(row.get("published_at"))
        if published_at and published_at > event_time:
            count += 1
    return count


def _headline_count(
    trending: Sequence[dict],
    recent: Sequence[dict],
    ticker_headlines: Mapping[str, Sequence[dict]],
) -> int:
    return len(trending) + len(recent) + sum(len(rows or []) for rows in ticker_headlines.values())


def _dedupe_headline_dicts(rows: Sequence[dict]) -> list[dict]:
    output = []
    seen = set()
    for row in rows:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        key = (title.lower(), str(row.get("source") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return output


def _dedupe_source_events(rows: Sequence[dict]) -> list[dict]:
    output = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("title") or "").lower(),
            str(row.get("source") or "").lower(),
            row.get("ticker"),
            row.get("section"),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return output


def _dataset_grade(report: Mapping) -> str:
    if report.get("news_mode") == "price-only":
        return "smoke_test_price_only"
    real_count = int(report.get("real_headline_count") or 0)
    synthetic_count = int(report.get("synthetic_headline_count") or 0)
    below_min = int(report.get("events_below_min_headline_coverage") or 0)
    violations = int(report.get("no_lookahead_violation_count") or 0)
    if violations:
        return "invalid_lookahead"
    if real_count and not synthetic_count and below_min == 0:
        return "news_enriched"
    if real_count and synthetic_count:
        return "mixed_real_and_synthetic_context"
    if real_count:
        return "partial_historical_context"
    if synthetic_count:
        return "synthetic_context_only"
    return "low_context"


def _payload_description(dataset_grade: str, start: date, end: date) -> str:
    if dataset_grade == "smoke_test_price_only":
        return (
            f"Daily price-only replay smoke-test events from {start.isoformat()} "
            f"through {end.isoformat()}."
        )
    if dataset_grade == "news_enriched":
        return (
            f"Daily historical replay events from {start.isoformat()} through "
            f"{end.isoformat()} with timestamped historical news context."
        )
    if dataset_grade == "partial_historical_context":
        return (
            f"Daily historical replay events from {start.isoformat()} through "
            f"{end.isoformat()} with timestamped historical news below the "
            "configured coverage threshold."
        )
    if dataset_grade == "synthetic_context_only":
        return (
            f"Daily historical replay events from {start.isoformat()} through "
            f"{end.isoformat()} with synthetic no-lookahead market summaries."
        )
    return (
        f"Daily historical replay events from {start.isoformat()} through "
        f"{end.isoformat()} with clearly labeled synthetic or mixed context."
    )


def _synthetic_policy(news_mode: str) -> str:
    if news_mode == "price-only":
        return "disabled; event file is a smoke test only"
    if news_mode == "synthetic":
        return "always generate no-lookahead summaries from OHLCV through the event date"
    if news_mode == "historical-first":
        return "use timestamped historical news first, then synthetic OHLCV summaries if context is below threshold"
    return "disabled unless imported headlines are explicitly marked synthetic"


def _normalize_tickers(values: Sequence[str]) -> list[str]:
    output = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)
    return output


def _extract_known_tickers(title: str, known_tickers: Sequence[str]) -> list[str]:
    text = f" {title.upper()} "
    matches = []
    for ticker in _normalize_tickers(known_tickers):
        token = ticker.replace(".", r"\.").replace("-", r"\-")
        if f" {ticker} " in text or f"({ticker})" in text or f"${ticker}" in text:
            matches.append(token.replace(r"\.", ".").replace(r"\-", "-"))
    return matches


def _event_datetime(day: date, event_time_utc: str) -> datetime:
    time_text = str(event_time_utc or "21:00:00Z").strip().upper()
    if time_text.endswith("Z"):
        time_text = time_text[:-1]
    parsed = time.fromisoformat(time_text)
    return datetime.combine(day, parsed, tzinfo=timezone.utc)


def _parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text[:10])


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_float(value) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _series_value(row, *names) -> float | None:
    lookup = {str(key).lower().replace(" ", "_"): key for key in getattr(row, "index", [])}
    for name in names:
        key = lookup.get(str(name).lower().replace(" ", "_"))
        if key is not None:
            value = _coerce_float(row.get(key))
            if value is not None:
                return value
    return None


def _return(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous) - 1


def _round(value, digits: int = 6):
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return round(parsed, digits)


def _direction_phrase(value) -> str:
    if value is None:
        return "with no prior close comparison"
    direction = "up" if value > 0 else "down" if value < 0 else "flat"
    return f"{direction} {abs(value) * 100:.2f}%"


def _direction_from_zero(value: float) -> str:
    return "above" if value > 0 else "below" if value < 0 else "near"


def _age_label(age_minutes: int) -> str:
    if age_minutes < 60:
        return f"{age_minutes} min ago"
    if age_minutes < 1440:
        return f"{age_minutes // 60}h ago"
    return f"{age_minutes // 1440}d ago"


if __name__ == "__main__":
    raise SystemExit(main())
