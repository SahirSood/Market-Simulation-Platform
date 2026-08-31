import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio import Portfolio
from risk import RiskLimits, risk_check_order


class PriceFeed:
    def get_price(self, ticker):
        return 100.0


def _bot(cash=10_000.0, positions=None):
    bot = SimpleNamespace()
    bot.portfolio = Portfolio(cash)
    for ticker, qty in (positions or {}).items():
        bot.portfolio.positions[ticker] = qty
    return bot


def _decision(action="BUY", ticker="NVDA", quantity=10, limit_price=100.0):
    return SimpleNamespace(
        action=action,
        ticker=ticker,
        quantity=quantity,
        limit_price=limit_price,
    )


def test_risk_check_approves_valid_buy():
    result = risk_check_order(_bot(), _decision(), PriceFeed())

    assert result.approved is True
    assert result.estimated_notional == 1000.0


def test_risk_check_rejects_cash_overdraft():
    result = risk_check_order(
        _bot(cash=500.0),
        _decision(action="BUY", quantity=10, limit_price=100.0),
        PriceFeed(),
    )

    assert result.approved is False
    assert result.reason == "insufficient cash after buy"


def test_risk_check_rejects_short_sale_when_disabled():
    result = risk_check_order(
        _bot(positions={"NVDA": 5}),
        _decision(action="SELL", quantity=10, limit_price=100.0),
        PriceFeed(),
        limits=RiskLimits(allow_short_selling=False),
    )

    assert result.approved is False
    assert "short selling disabled" in result.reason


def test_risk_check_allows_bounded_short_sale_by_default():
    result = risk_check_order(
        _bot(positions={"NVDA": 5}),
        _decision(action="SELL", quantity=10, limit_price=100.0),
        PriceFeed(),
    )

    assert result.approved is True


def test_risk_check_uses_market_price_for_market_order():
    result = risk_check_order(
        _bot(),
        _decision(action="BUY", quantity=5, limit_price=None),
        PriceFeed(),
        limits=RiskLimits(max_order_notional=1000.0),
    )

    assert result.approved is True
    assert result.estimated_price == 100.0


def test_short_risk_uses_live_price_when_sell_limit_is_lower():
    result = risk_check_order(
        _bot(),
        _decision(action="SELL", quantity=10, limit_price=90.0),
        PriceFeed(),
    )

    assert result.approved is True
    assert result.estimated_price == 100.0
    assert result.estimated_notional == 1000.0


def test_risk_check_rejects_ticker_outside_tradable_universe():
    result = risk_check_order(
        _bot(),
        _decision(action="BUY", ticker="NOTREAL", quantity=5, limit_price=100.0),
        PriceFeed(),
    )

    assert result.approved is False
    assert "outside tradable universe" in result.reason


def test_risk_check_rejects_benchmark_context_symbol():
    result = risk_check_order(
        _bot(),
        _decision(action="BUY", ticker="SPY", quantity=5, limit_price=100.0),
        PriceFeed(),
    )

    assert result.approved is False
    assert "outside tradable universe" in result.reason


def test_risk_check_uses_dynamic_tradable_universe_from_price_feed():
    class DynamicPriceFeed(PriceFeed):
        def get_tradable_tickers(self):
            return ["AAPL", "PLTR"]

    result = risk_check_order(
        _bot(),
        _decision(action="BUY", ticker="PLTR", quantity=5, limit_price=100.0),
        DynamicPriceFeed(),
    )

    assert result.approved is True
