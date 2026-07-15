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


def _decision(action="BUY", ticker="AAPL", quantity=10, limit_price=100.0):
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


def test_risk_check_rejects_short_sale_by_default():
    result = risk_check_order(
        _bot(positions={"AAPL": 5}),
        _decision(action="SELL", quantity=10, limit_price=100.0),
        PriceFeed(),
    )

    assert result.approved is False
    assert "short selling disabled" in result.reason


def test_risk_check_uses_market_price_for_market_order():
    result = risk_check_order(
        _bot(),
        _decision(action="BUY", quantity=5, limit_price=None),
        PriceFeed(),
        limits=RiskLimits(max_order_notional=1000.0),
    )

    assert result.approved is True
    assert result.estimated_price == 100.0
