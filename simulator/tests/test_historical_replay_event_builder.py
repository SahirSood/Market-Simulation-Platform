import json
import os
import sys
from datetime import date, datetime, timezone


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from replay_workflow import load_replay_event_file, validate_replay_events
from scripts.build_historical_replay_events import (
    PriceRow,
    build_historical_replay_payload,
    load_price_file,
    load_news_file,
    write_json,
)


def _history():
    return {
        "AAPL": [
            PriceRow("AAPL", date(2026, 1, 1), 100, 101, 99, 100, 1_000_000),
            PriceRow("AAPL", date(2026, 1, 2), 101, 103, 100, 102, 1_200_000),
            PriceRow("AAPL", date(2026, 1, 3), 102, 103, 100, 101, 900_000),
        ],
        "SPY": [
            PriceRow("SPY", date(2026, 1, 1), 500, 502, 499, 500, 10_000_000),
            PriceRow("SPY", date(2026, 1, 2), 503, 506, 502, 505, 11_000_000),
            PriceRow("SPY", date(2026, 1, 3), 504, 505, 499, 500, 12_000_000),
        ],
        "QQQ": [
            PriceRow("QQQ", date(2026, 1, 1), 400, 401, 399, 400, 8_000_000),
            PriceRow("QQQ", date(2026, 1, 2), 402, 406, 401, 405, 8_500_000),
            PriceRow("QQQ", date(2026, 1, 3), 404, 405, 398, 399, 9_000_000),
        ],
        "TLT": [
            PriceRow("TLT", date(2026, 1, 1), 90, 91, 89, 90, 4_000_000),
            PriceRow("TLT", date(2026, 1, 2), 89, 90, 88, 89, 4_500_000),
            PriceRow("TLT", date(2026, 1, 3), 90, 92, 90, 92, 5_000_000),
        ],
    }


def _all_headlines(event):
    rows = []
    rows.extend(event.get("trending_headlines") or [])
    rows.extend(event.get("recent_headlines") or [])
    for ticker_rows in (event.get("ticker_headlines") or {}).values():
        rows.extend(ticker_rows)
    return rows


def test_builder_adds_synthetic_context_and_benchmark_fields():
    payload, report = build_historical_replay_payload(
        price_history=_history(),
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
        tickers=["AAPL", "SPY"],
        benchmarks=["SPY", "QQQ", "TLT"],
        news_mode="synthetic",
        generated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )

    assert payload["config"]["dataset_grade"] == "synthetic_context_only"
    assert report["dataset_grade"] == "synthetic_context_only"
    assert len(payload["events"]) == 3

    second_event = payload["events"][1]
    assert second_event["benchmark_prices"]["SPY"] == 505
    assert second_event["benchmark_returns"]["SPY"] == 0.01
    assert second_event["market_regime"]["risk_regime"] == "risk_on"
    assert second_event["news_coverage"]["synthetic_headline_count"] > 0

    for event in payload["events"]:
        event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        assert validate_replay_events([event]) == [event]
        assert _all_headlines(event)
        for headline in _all_headlines(event):
            published_at = datetime.fromisoformat(
                headline["published_at"].replace("Z", "+00:00")
            )
            assert headline["synthetic"] is True
            assert published_at <= event_time


def test_builder_filters_future_news_file_headlines(tmp_path):
    news_path = tmp_path / "headlines.json"
    news_path.write_text(
        json.dumps({
            "headlines": [
                {
                    "title": "AAPL raises guidance after revenue acceleration",
                    "source": "UnitWire",
                    "published_at": "2026-01-02T20:00:00Z",
                    "tickers": ["AAPL"],
                    "category": "company",
                    "url": "https://example.com/aapl-guidance",
                },
                {
                    "title": "AAPL future headline should not appear",
                    "source": "UnitWire",
                    "published_at": "2026-01-03T22:00:00Z",
                    "tickers": ["AAPL"],
                    "category": "company",
                },
            ]
        }),
        encoding="utf-8",
    )
    news_items = load_news_file(news_path, ["AAPL", "SPY"])

    payload, report = build_historical_replay_payload(
        price_history=_history(),
        start=date(2026, 1, 2),
        end=date(2026, 1, 3),
        tickers=["AAPL", "SPY"],
        benchmarks=["SPY"],
        news_mode="news-file",
        news_items=news_items,
        news_lookback_hours=24,
        min_headlines_per_event=1,
        generated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )

    serialized = json.dumps(payload)
    assert "raises guidance" in serialized
    assert "future headline" not in serialized
    assert report["no_lookahead_violation_count"] == 0
    assert report["dataset_grade"] == "partial_historical_context"
    assert report["events_below_min_headline_coverage"] == 1


def test_price_only_output_is_marked_as_smoke_test(tmp_path):
    payload, report = build_historical_replay_payload(
        price_history=_history(),
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
        tickers=["AAPL", "SPY"],
        benchmarks=["SPY"],
        news_mode="price-only",
        generated_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    output = tmp_path / "generated" / "price_only.json"
    write_json(output, payload)
    name, config, events = load_replay_event_file(
        "generated/price_only.json",
        root=tmp_path,
    )

    assert name == payload["name"]
    assert config["dataset_grade"] == "smoke_test_price_only"
    assert report["dataset_grade"] == "smoke_test_price_only"
    assert events[0]["trending_headlines"] == []
    assert events[0]["recent_headlines"] == []
    assert events[0]["expected_notes"]


def test_price_file_loader_accepts_existing_replay_event_json(tmp_path):
    source = tmp_path / "fixture.json"
    source.write_text(
        json.dumps({
            "name": "Fixture",
            "events": [
                {
                    "timestamp": "2026-01-01T21:00:00Z",
                    "prices": {"AAPL": 100.0, "SPY": 500.0},
                    "ohlcv": {
                        "AAPL": {
                            "open": 99.0,
                            "high": 101.0,
                            "low": 98.0,
                            "close": 100.0,
                            "volume": 1000,
                        }
                    },
                }
            ],
        }),
        encoding="utf-8",
    )

    history = load_price_file(source)

    assert history["AAPL"][0].close == 100.0
    assert history["AAPL"][0].volume == 1000
    assert history["SPY"][0].open == 500.0
