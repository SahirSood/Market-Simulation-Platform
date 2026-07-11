import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import OrderDecision
from portfolio import FillRecord
from scheduler import BotScheduler


def _hold_decision():
    return OrderDecision(
        action="HOLD",
        ticker=None,
        quantity=None,
        limit_price=None,
        reasoning="test hold",
        headline_used=None,
    )


def _buy_decision():
    return OrderDecision(
        action="BUY",
        ticker="AAPL",
        quantity=100,
        limit_price=150.0,
        reasoning="bullish",
        headline_used="headline",
    )


def _make_bot(name, decision):
    bot = MagicMock()
    bot.name = name
    bot.bot_id = f"{name.lower()}-001"
    bot.decide.return_value = decision
    bot.price_feed.get_price.return_value = 150.0
    bot.portfolio = MagicMock()
    return bot


def _make_scheduler(bots, reasoning_log=None):
    noise_pool = MagicMock()
    noise_pool.trader_count = 10
    engine_adapter = MagicMock()
    engine_adapter.submit.return_value = (1, [])
    return (
        BotScheduler(
            bots,
            noise_pool,
            engine_adapter,
            reasoning_log,
            bot_cycle_mins=60,
            noise_interval_secs=60,
        ),
        noise_pool,
        engine_adapter,
    )


def test_hold_decision_logs_without_submitting_order():
    reasoning_log = MagicMock()
    bot = _make_bot("BearBot", _hold_decision())
    scheduler, _, engine_adapter = _make_scheduler([bot], reasoning_log)

    scheduler._run_bot(bot)

    engine_adapter.submit.assert_not_called()
    reasoning_log.log.assert_called_once()
    assert reasoning_log.log.call_args.kwargs["fills"] == []


def test_buy_decision_submits_limit_order_and_logs_fills():
    fill = FillRecord(order_id=1, ticker="AAPL", side="BUY", quantity=100, price=150.0)
    reasoning_log = MagicMock()
    bot = _make_bot("DegenBot", _buy_decision())
    scheduler, _, engine = _make_scheduler([bot], reasoning_log)
    engine.submit.return_value = (1, [fill])

    scheduler._run_bot(bot)

    engine.submit.assert_called_once_with(
        ticker="AAPL",
        side="BUY",
        order_type="LIMIT",
        price=150.0,
        quantity=100,
        bot_id="degenbot-001",
    )
    bot.portfolio.apply_fill.assert_called_once_with(fill, strict=False)
    reasoning_log.log.assert_called_once_with(bot, bot.decide.return_value, [fill])


def test_bot_exception_does_not_propagate():
    crash_bot = MagicMock()
    crash_bot.name = "CrashBot"
    crash_bot.bot_id = "crash-001"
    crash_bot.decide.side_effect = RuntimeError("LLM failed")
    ok_bot = _make_bot("OkBot", _hold_decision())
    scheduler, _, _ = _make_scheduler([crash_bot, ok_bot])

    scheduler._run_bot(crash_bot)
    scheduler._run_bot(ok_bot)

    ok_bot.decide.assert_called_once()


def test_market_order_uses_price_feed_fallback_price():
    market_decision = OrderDecision(
        action="BUY",
        ticker="NVDA",
        quantity=50,
        limit_price=None,
        reasoning="momentum",
        headline_used=None,
    )
    bot = _make_bot("DegenBot", market_decision)
    bot.price_feed.get_price.return_value = 489.0
    scheduler, _, engine = _make_scheduler([bot])

    scheduler._run_bot(bot)

    assert engine.submit.call_args.kwargs["order_type"] == "MARKET"
    assert engine.submit.call_args.kwargs["price"] == 489.0


def test_start_runs_noise_pool_immediately(monkeypatch):
    bot = _make_bot("BearBot", _hold_decision())
    scheduler, noise_pool, _ = _make_scheduler([bot])

    monkeypatch.setattr(scheduler, "_schedule_bot", MagicMock())
    scheduler.start()
    scheduler.stop()

    noise_pool.tick.assert_called_once()
