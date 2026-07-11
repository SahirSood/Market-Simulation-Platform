import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from price_feed import PriceFeed, PriceFeedError


class FakeFastInfo:
    last_price = 123.45
    open = 120.0
    day_high = 124.0
    day_low = 119.5
    previous_close = 121.0
    three_month_average_volume = 1000


class FakeTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.fast_info = FakeFastInfo()


def test_price_feed_fetches_and_caches_prices(monkeypatch):
    calls = []

    def fake_ticker(ticker):
        calls.append(ticker)
        return FakeTicker(ticker)

    monkeypatch.setattr("price_feed.yf.Ticker", fake_ticker)

    feed = PriceFeed()
    assert feed.get_price("AAPL") == 123.45
    assert feed.get_price("AAPL") == 123.45
    assert calls == ["AAPL"]
    assert feed.get_active_tickers() == ["AAPL"]


def test_price_feed_returns_stale_cache_when_refresh_fails(monkeypatch):
    feed = PriceFeed()
    feed._cache["AAPL"] = {
        "price": 150.0,
        "ohlcv": {"open": 149.0},
        "timestamp": time.time() - 9999,
    }

    def failing_ticker(ticker):
        raise RuntimeError("network down")

    monkeypatch.setattr("price_feed.yf.Ticker", failing_ticker)

    assert feed.get_price("AAPL") == 150.0
    assert feed.get_ohlcv("AAPL") == {"open": 149.0}


def test_price_feed_raises_without_cache_when_fetch_fails(monkeypatch):
    def failing_ticker(ticker):
        raise RuntimeError("network down")

    monkeypatch.setattr("price_feed.yf.Ticker", failing_ticker)

    feed = PriceFeed()
    try:
        feed.get_price("AAPL")
    except PriceFeedError as exc:
        assert "Failed to fetch price for AAPL" in str(exc)
    else:
        raise AssertionError("Expected PriceFeedError")
