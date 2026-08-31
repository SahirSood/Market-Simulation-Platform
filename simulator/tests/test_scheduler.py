import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_bot import OrderDecision
import scheduler as scheduler_module
from market_hours import MarketHoursConfig
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
        ticker="NVDA",
        quantity=100,
        limit_price=150.0,
        reasoning="bullish",
        headline_used="headline",
    )


def _make_bot(name, decision, provider="claude"):
    bot = MagicMock()
    bot.name = name
    bot.bot_id = f"{name.lower()}-001"
    bot.llm_provider = provider
    bot.decide.return_value = decision
    bot.price_feed.get_price.return_value = 150.0
    bot.portfolio = MagicMock()
    bot.portfolio.snapshot.return_value = {
        "cash": 100_000.0,
        "positions": {},
        "cost_basis": {},
    }
    return bot


def _make_scheduler(bots, reasoning_log=None):
    noise_pool = MagicMock()
    noise_pool.trader_count = 10
    engine_adapter = MagicMock()
    engine_adapter.submit.return_value = (1, [])
    engine_adapter.drain_fills.return_value = []
    scheduler = BotScheduler(
        bots,
        noise_pool,
        engine_adapter,
        reasoning_log,
        bot_cycle_mins=60,
        noise_interval_secs=60,
    )
    scheduler._market_hours = MarketHoursConfig(enabled=False)
    return scheduler, noise_pool, engine_adapter


def test_hold_decision_logs_without_submitting_order():
    reasoning_log = MagicMock()
    bot = _make_bot("BearBot", _hold_decision())
    scheduler, _, engine_adapter = _make_scheduler([bot], reasoning_log)

    scheduler._run_bot(bot)

    engine_adapter.submit.assert_not_called()
    reasoning_log.log.assert_called_once_with(bot, bot.decide.return_value, fills=[])
    reasoning_log.record_execution_order.assert_not_called()


def test_buy_decision_submits_limit_order_and_logs_fills():
    fill = FillRecord(order_id=1, ticker="NVDA", side="BUY", quantity=100, price=150.0)
    reasoning_log = MagicMock()
    reasoning_log.log.return_value = 7
    bot = _make_bot("DegenBot", _buy_decision())
    scheduler, _, engine = _make_scheduler([bot], reasoning_log)
    engine.submit.return_value = (1, [fill])

    scheduler._run_bot(bot)

    engine.submit.assert_called_once_with(
        ticker="NVDA",
        side="BUY",
        order_type="LIMIT",
        price=150.0,
        quantity=100,
        bot_id="degenbot-001",
    )
    bot.portfolio.apply_fill.assert_called_once_with(fill, strict=False)
    reasoning_log.log.assert_called_once_with(bot, bot.decide.return_value, fills=[fill])
    reasoning_log.record_execution_order.assert_called_once()
    ledger_call = reasoning_log.record_execution_order.call_args.kwargs
    assert ledger_call["bot"] is bot
    assert ledger_call["decision"] is bot.decide.return_value
    assert ledger_call["engine_order_id"] == 1
    assert ledger_call["order_type"] == "LIMIT"
    assert ledger_call["submitted_price"] == 150.0
    assert ledger_call["fills"] == [fill]
    assert ledger_call["decision_id"] == 7


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


def test_oversized_buy_is_autosized_to_risk_notional_cap():
    oversized = OrderDecision(
        action="BUY",
        ticker="MSFT",
        quantity=100,
        limit_price=None,
        reasoning="bullish but too large",
        headline_used=None,
    )
    fill = FillRecord(order_id=1, ticker="MSFT", side="BUY", quantity=50, price=500.0)
    reasoning_log = MagicMock()
    bot = _make_bot("AnalystBot", oversized)
    bot.price_feed.get_price.return_value = 500.0
    scheduler, _, engine = _make_scheduler([bot], reasoning_log)
    engine.submit.return_value = (1, [fill])

    scheduler._run_bot(bot)

    assert engine.submit.call_args.kwargs["quantity"] == 50
    logged_decision = reasoning_log.log.call_args.args[1]
    assert logged_decision.quantity == 50
    assert "Risk auto-sized quantity from 100 to 50" in logged_decision.reasoning


def test_stale_limit_price_is_refreshed_to_marketable_order():
    stale_limit = OrderDecision(
        action="BUY",
        ticker="NVDA",
        quantity=10,
        limit_price=100.0,
        reasoning="buy with stale limit",
        headline_used=None,
    )
    reasoning_log = MagicMock()
    bot = _make_bot("ContrarianBot", stale_limit)
    bot.price_feed.get_price.return_value = 200.0
    scheduler, _, engine = _make_scheduler([bot], reasoning_log)

    scheduler._run_bot(bot)

    assert engine.submit.call_args.kwargs["order_type"] == "MARKET"
    assert engine.submit.call_args.kwargs["price"] == 200.0
    logged_decision = reasoning_log.log.call_args.args[1]
    assert logged_decision.limit_price is None
    assert "stale limit" in logged_decision.reasoning


def test_risk_rejection_logs_hold_without_submitting_order():
    risky_decision = OrderDecision(
        action="BUY",
        ticker="NOTREAL",
        quantity=10,
        limit_price=150.0,
        reasoning="bad ticker",
        headline_used="headline",
    )
    reasoning_log = MagicMock()
    reasoning_log.log.return_value = 11
    bot = _make_bot("DegenBot", risky_decision)
    scheduler, _, engine = _make_scheduler([bot], reasoning_log)

    scheduler._run_bot(bot)

    engine.submit.assert_not_called()
    logged_decision = reasoning_log.log.call_args.args[1]
    assert logged_decision.action == "HOLD"
    assert logged_decision.hold_cause == "risk_limit"
    assert "Risk check rejected" in logged_decision.reasoning
    reasoning_log.record_execution_order.assert_called_once()
    ledger_call = reasoning_log.record_execution_order.call_args.kwargs
    assert ledger_call["decision"] is risky_decision
    assert ledger_call["engine_order_id"] is None
    assert ledger_call["status"] == "REJECTED"
    assert "tradable universe" in ledger_call["rejection_reason"]
    assert ledger_call["decision_id"] == 11


def test_start_runs_noise_pool_immediately(monkeypatch):
    bot = _make_bot("BearBot", _hold_decision())
    scheduler, noise_pool, _ = _make_scheduler([bot])

    monkeypatch.setattr(scheduler, "_schedule_bot", MagicMock())
    scheduler.start()
    scheduler.stop()

    noise_pool.tick.assert_called_once()


def test_passive_fills_update_portfolio_and_durable_ledger():
    reasoning_log = MagicMock()
    bot = _make_bot("AnalystBot", _hold_decision(), provider="openai")
    scheduler, _, engine = _make_scheduler([bot], reasoning_log)
    passive_fill = FillRecord(
        order_id=91,
        ticker="AAPL",
        side="BUY",
        quantity=25,
        price=149.5,
    )
    engine.drain_fills.return_value = [passive_fill]

    scheduler._settle_passive_fills()

    bot.portfolio.apply_fill.assert_called_once_with(passive_fill, strict=False)
    reasoning_log.record_passive_fills.assert_called_once_with(bot, [passive_fill])
    activity = reasoning_log.record_agent_activity.call_args.kwargs
    assert activity["stage"] == "passive_fill"
    assert activity["metadata"]["fill_qty_total"] == 25


def test_provider_budget_blocks_only_matching_provider(monkeypatch):
    monkeypatch.setattr(scheduler_module, "LLM_COST_GUARD_ENABLED", True)
    monkeypatch.setattr(scheduler_module, "LLM_DAILY_DECISION_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_MONTHLY_DECISION_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_CLAUDE_DAILY_CALL_BUDGET", 1)
    monkeypatch.setattr(scheduler_module, "LLM_CLAUDE_MONTHLY_CALL_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_OPENAI_DAILY_CALL_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_OPENAI_MONTHLY_CALL_BUDGET", 0)

    reasoning_log = MagicMock()
    reasoning_log.count_decisions.side_effect = (
        lambda since=None, llm_provider=None, billable_only=False: (
            1 if llm_provider == "claude" and billable_only else 0
        )
    )
    claude_bot = _make_bot("ClaudeBot", _hold_decision(), provider="claude")
    openai_bot = _make_bot("OpenAIBot", _hold_decision(), provider="openai")
    scheduler, _, _ = _make_scheduler([claude_bot, openai_bot], reasoning_log)

    assert scheduler._decision_budget_exhausted(claude_bot) is True
    assert scheduler._decision_budget_exhausted(openai_bot) is False
    status = scheduler.status()
    assert status["provider_budgets"]["claude"]["exhausted"] is True
    assert status["provider_budgets"]["openai"]["exhausted"] is False


def test_spend_budget_blocks_projected_paid_call(monkeypatch):
    monkeypatch.setattr(scheduler_module, "LLM_COST_GUARD_ENABLED", True)
    monkeypatch.setattr(scheduler_module, "LLM_DAILY_DECISION_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_MONTHLY_DECISION_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_CLAUDE_DAILY_CALL_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_CLAUDE_MONTHLY_CALL_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_OPENAI_DAILY_CALL_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_OPENAI_MONTHLY_CALL_BUDGET", 0)
    monkeypatch.setattr(scheduler_module, "LLM_DAILY_SPEND_LIMIT_USD", 1.0)
    monkeypatch.setattr(scheduler_module, "LLM_MONTHLY_SPEND_LIMIT_USD", 20.0)

    reasoning_log = MagicMock()
    reasoning_log.count_decisions.return_value = 0
    reasoning_log.sum_estimated_llm_cost.side_effect = (
        lambda since=None, llm_provider=None: 0.99
    )
    bot = _make_bot("ClaudeBot", _hold_decision(), provider="claude")
    scheduler, _, _ = _make_scheduler([bot], reasoning_log)

    assert scheduler._decision_budget_exhausted(bot) is True
    assert scheduler.status()["spend_budget_exhausted"] is True
