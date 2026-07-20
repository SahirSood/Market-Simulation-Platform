import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import liquidity
from liquidity import seed_order_book_liquidity


class PriceFeed:
    def get_price(self, ticker):
        if ticker == "SKIP":
            raise RuntimeError("price unavailable")
        return {"AAPL": 100.0, "MSFT": 200.0}[ticker]


class Adapter:
    def __init__(self):
        self.calls = []

    def seed_liquidity(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["levels"] * 2


def test_seed_order_book_liquidity_uses_configured_tickers(monkeypatch):
    monkeypatch.setattr(liquidity, "SEED_LIQUIDITY_ON_STARTUP", True)
    monkeypatch.setattr(liquidity, "TRADABLE_TICKERS", ("AAPL", "MSFT"))
    monkeypatch.setattr(liquidity, "SEED_LIQUIDITY_LEVELS", 2)
    monkeypatch.setattr(liquidity, "SEED_LIQUIDITY_QTY", 300)
    monkeypatch.setattr(liquidity, "SEED_LIQUIDITY_SPREAD_PCT", 0.01)
    adapter = Adapter()

    seeded = seed_order_book_liquidity(PriceFeed(), adapter)

    assert [row["ticker"] for row in seeded] == ["AAPL", "MSFT"]
    assert [call["ticker"] for call in adapter.calls] == ["AAPL", "MSFT"]
    assert adapter.calls[0]["levels"] == 2
    assert adapter.calls[0]["quantity"] == 300
    assert adapter.calls[0]["spread_pct"] == 0.01


def test_seed_order_book_liquidity_skips_price_failures(monkeypatch):
    monkeypatch.setattr(liquidity, "SEED_LIQUIDITY_ON_STARTUP", True)
    monkeypatch.setattr(liquidity, "TRADABLE_TICKERS", ("AAPL", "SKIP"))
    adapter = Adapter()

    seeded = seed_order_book_liquidity(PriceFeed(), adapter)

    assert [row["ticker"] for row in seeded] == ["AAPL"]
    assert [call["ticker"] for call in adapter.calls] == ["AAPL"]
