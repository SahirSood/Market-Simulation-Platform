"""
BotScheduler — orchestrates all agents on independent timers.

  - AI bots:       every BOT_CYCLE_MINS, staggered 60s apart
  - Noise traders: every NOISE_INTERVAL (900 s), fires once immediately on start
  - Clean shutdown via stop() + SIGINT/SIGTERM (wired up in main.py)

Each bot runs in its own daemon thread. A single threading.Lock in EngineAdapter
guards engine access; Portfolio has its own lock for position mutations.
"""
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

from config import (
    BOT_CYCLE_MINS,
    LLM_CLAUDE_DAILY_CALL_BUDGET,
    LLM_CLAUDE_MONTHLY_CALL_BUDGET,
    LLM_COST_GUARD_ENABLED,
    LLM_DAILY_DECISION_BUDGET,
    LLM_MONTHLY_DECISION_BUDGET,
    LLM_OPENAI_DAILY_CALL_BUDGET,
    LLM_OPENAI_MONTHLY_CALL_BUDGET,
    MARKET_CLOSE_TIME,
    MARKET_HOURS_ONLY,
    MARKET_OPEN_TIME,
    MARKET_TIMEZONE,
    NOISE_INTERVAL,
)
from base_bot import OrderDecision
from market_hours import MarketHoursConfig, is_market_open
from risk import RiskLimits, risk_check_order

logger = logging.getLogger(__name__)


class BotScheduler:
    def __init__(
        self,
        bots,                                      # list[BaseBot subclasses]
        noise_pool,                                # NoiseTraderPool
        engine_adapter,                            # EngineAdapter
        reasoning_log,                             # ReasoningLog (or None)
        event_callback: Optional[Callable] = None, # called with event dict on each decision
        bot_cycle_mins: float = BOT_CYCLE_MINS,
        noise_interval_secs: float = NOISE_INTERVAL,
        initial_bot_delay_secs: float = 0.0,
        risk_limits: Optional[RiskLimits] = None,
        research_coordinator=None,
    ):
        self._bots            = bots
        self._noise_pool      = noise_pool
        self._engine_adapter  = engine_adapter
        self._reasoning_log   = reasoning_log
        self._event_callback  = event_callback
        self._bot_cycle_mins  = bot_cycle_mins
        self._noise_interval_secs = noise_interval_secs
        self._initial_bot_delay_secs = max(0.0, float(initial_bot_delay_secs or 0.0))
        self._risk_limits = risk_limits or RiskLimits()
        self._research_coordinator = research_coordinator
        self._market_hours = MarketHoursConfig(
            enabled=MARKET_HOURS_ONLY,
            timezone=MARKET_TIMEZONE,
            open_time=MARKET_OPEN_TIME,
            close_time=MARKET_CLOSE_TIME,
        )
        for bot in self._bots:
            bot.risk_limits = self._risk_limits
        self._timers:  list[threading.Timer] = []
        self._running: bool   = False
        self._stop_event      = threading.Event()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._stop_event.clear()

        # Stagger bot starts by 60s each to avoid simultaneous LLM API bursts
        for i, bot in enumerate(self._bots):
            self._schedule_bot(bot, delay=self._initial_bot_delay_secs + i * 60)

        # Noise traders fire immediately, then every NOISE_INTERVAL
        self._run_noise_and_reschedule()

        logger.info(
            f"[BotScheduler] Started: {len(self._bots)} bots, "
            f"noise pool ({self._noise_pool.trader_count} traders)"
        )

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        for t in self._timers:
            t.cancel()
        self._timers.clear()
        logger.info("[BotScheduler] Stopped")

    # ── Scheduling helpers ────────────────────────────────────────────────────

    def _schedule_bot(self, bot, delay: float) -> None:
        def run():
            if self._stop_event.is_set():
                return
            self._run_bot(bot)
            if self._running:
                self._schedule_bot(bot, delay=self._bot_cycle_mins * 60)

        t = threading.Timer(delay, run)
        t.daemon = True
        t.start()
        self._timers.append(t)

    def _run_noise_and_reschedule(self) -> None:
        if self._stop_event.is_set():
            return
        try:
            if is_market_open(self._market_hours):
                self._noise_pool.tick()
            else:
                logger.info("[BotScheduler] Noise tick skipped outside market hours")
        except Exception as e:
            logger.error(f"[BotScheduler] Noise tick failed: {e}")
        if self._running:
            t = threading.Timer(self._noise_interval_secs, self._run_noise_and_reschedule)
            t.daemon = True
            t.start()
            self._timers.append(t)

    # ── Bot execution ─────────────────────────────────────────────────────────

    def _run_bot(self, bot) -> None:
        """
        One full decision cycle for an AI bot.
        Any exception is caught and logged — the scheduler must never die
        because one bot has a bad day.
        """
        try:
            if not is_market_open(self._market_hours):
                logger.info(f"[{bot.name}] Skipped outside configured market hours")
                return
            if self._decision_budget_exhausted(bot):
                logger.warning(f"[{bot.name}] Skipped because LLM decision budget is exhausted")
                return

            decision = bot.decide()
            self._request_research(bot, decision)

            if decision.action == "HOLD":
                logger.info(f"[{bot.name}] HOLD — no order submitted")
                if self._reasoning_log:
                    self._reasoning_log.log(bot, decision, fills=[])
                if self._event_callback:
                    self._event_callback({
                        "type":       "decision",
                        "bot_id":     bot.bot_id,
                        "bot_name":   bot.name,
                        "action":     "HOLD",
                        "ticker":     None,
                        "quantity":   None,
                        "fill_count": 0,
                        "reasoning":  decision.reasoning,
                        "timestamp":  datetime.now(timezone.utc).isoformat(),
                    })
                return

            decision = self._normalize_stale_limit_price(bot, decision)
            decision = self._autosize_order(bot, decision)

            risk_result = risk_check_order(
                bot=bot,
                decision=decision,
                price_feed=bot.price_feed,
                limits=self._risk_limits,
            )
            if not risk_result.approved:
                logger.warning(
                    f"[{bot.name}] Risk rejected {decision.action} "
                    f"{decision.quantity} {decision.ticker}: {risk_result.reason}"
                )
                decision = self._risk_rejection_decision(decision, risk_result)
                if self._reasoning_log:
                    self._reasoning_log.log(bot, decision, fills=[])
                if self._event_callback:
                    self._event_callback({
                        "type":       "decision",
                        "bot_id":     bot.bot_id,
                        "bot_name":   bot.name,
                        "action":     "HOLD",
                        "ticker":     None,
                        "quantity":   None,
                        "fill_count": 0,
                        "reasoning":  decision.reasoning,
                        "timestamp":  datetime.now(timezone.utc).isoformat(),
                    })
                return

            order_type = "LIMIT" if decision.limit_price else "MARKET"
            price = (decision.limit_price
                     or bot.price_feed.get_price(decision.ticker))

            order_id, fills = self._engine_adapter.submit(
                ticker=decision.ticker,
                side=decision.action,
                order_type=order_type,
                price=price,
                quantity=decision.quantity,
                bot_id=bot.bot_id,
            )

            for fill in fills:
                bot.portfolio.apply_fill(fill, strict=False)

            if self._reasoning_log:
                self._reasoning_log.log(bot, decision, fills)

            if self._event_callback:
                self._event_callback({
                    "type":       "trade" if fills else "decision",
                    "bot_id":     bot.bot_id,
                    "bot_name":   bot.name,
                    "action":     decision.action,
                    "ticker":     decision.ticker,
                    "quantity":   decision.quantity,
                    "fill_count": len(fills),
                    "reasoning":  decision.reasoning,
                    "timestamp":  datetime.now(timezone.utc).isoformat(),
                })

            logger.info(
                f"[{bot.name}] {decision.action} {decision.quantity} "
                f"{decision.ticker} @ {price:.2f} "
                f"— {len(fills)} fill(s) | "
                f"reason: {decision.reasoning}"
            )

        except Exception as e:
            logger.error(
                f"[{bot.name}] Decision cycle failed: {e}",
                exc_info=True,
            )

    def _request_research(self, bot, decision: OrderDecision) -> None:
        if self._research_coordinator is None:
            return
        try:
            queued = self._research_coordinator.request_from_decision(bot, decision)
            if queued:
                logger.info("[%s] Queued research for: %s", bot.name, ", ".join(queued))
        except Exception as exc:
            logger.warning("[%s] Research queue request failed: %s", bot.name, exc)

    def _decision_budget_exhausted(self, bot=None) -> bool:
        if not LLM_COST_GUARD_ENABLED:
            return False

        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if LLM_DAILY_DECISION_BUDGET > 0:
            if self._billable_decision_count(day_start) >= LLM_DAILY_DECISION_BUDGET:
                return True
        if LLM_MONTHLY_DECISION_BUDGET > 0:
            if self._billable_decision_count(month_start) >= LLM_MONTHLY_DECISION_BUDGET:
                return True

        provider = str(getattr(bot, "llm_provider", "") or "").lower()
        limits = self._provider_budget_limits(provider)
        if provider and limits["daily"] > 0:
            if self._billable_decision_count(day_start, provider) >= limits["daily"]:
                return True
        if provider and limits["monthly"] > 0:
            if self._billable_decision_count(month_start, provider) >= limits["monthly"]:
                return True
        return False

    def _billable_decision_count(self, since: datetime, llm_provider: str | None = None) -> int:
        counter = getattr(self._reasoning_log, "count_decisions", None)
        if not callable(counter):
            return 0
        try:
            value = counter(
                since=since,
                llm_provider=llm_provider,
                billable_only=True,
            )
        except TypeError:
            try:
                value = counter(since=since)
            except Exception:
                return 0
        except Exception as exc:
            logger.warning("[BotScheduler] Decision budget count failed: %s", exc)
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _provider_budget_limits(provider: str | None) -> dict:
        key = str(provider or "").lower()
        if key == "claude":
            return {
                "daily": LLM_CLAUDE_DAILY_CALL_BUDGET,
                "monthly": LLM_CLAUDE_MONTHLY_CALL_BUDGET,
            }
        if key == "openai":
            return {
                "daily": LLM_OPENAI_DAILY_CALL_BUDGET,
                "monthly": LLM_OPENAI_MONTHLY_CALL_BUDGET,
            }
        return {"daily": 0, "monthly": 0}

    def status(self) -> dict:
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        daily_calls = self._billable_decision_count(day_start)
        monthly_calls = self._billable_decision_count(month_start)
        provider_budgets = {}
        for provider in ("claude", "openai"):
            limits = self._provider_budget_limits(provider)
            provider_daily = self._billable_decision_count(day_start, provider)
            provider_monthly = self._billable_decision_count(month_start, provider)
            provider_budgets[provider] = {
                "daily_billable_calls": provider_daily,
                "monthly_billable_calls": provider_monthly,
                "daily_limit": limits["daily"],
                "monthly_limit": limits["monthly"],
                "exhausted": (
                    (limits["daily"] > 0 and provider_daily >= limits["daily"])
                    or (limits["monthly"] > 0 and provider_monthly >= limits["monthly"])
                ),
            }
        return {
            "running": self._running,
            "market_hours_only": MARKET_HOURS_ONLY,
            "market_open": is_market_open(self._market_hours),
            "market_timezone": MARKET_TIMEZONE,
            "market_open_time": MARKET_OPEN_TIME,
            "market_close_time": MARKET_CLOSE_TIME,
            "cost_guard_enabled": LLM_COST_GUARD_ENABLED,
            "daily_decision_budget": LLM_DAILY_DECISION_BUDGET,
            "monthly_decision_budget": LLM_MONTHLY_DECISION_BUDGET,
            "daily_billable_calls": daily_calls,
            "monthly_billable_calls": monthly_calls,
            "provider_budgets": provider_budgets,
            "decision_budget_exhausted": self._decision_budget_exhausted(),
        }

    def _normalize_stale_limit_price(self, bot, decision: OrderDecision) -> OrderDecision:
        action = str(getattr(decision, "action", "") or "").upper()
        ticker = getattr(decision, "ticker", None)
        limit_price = getattr(decision, "limit_price", None)
        if action not in {"BUY", "SELL"} or not ticker or limit_price is None:
            return decision

        try:
            live_price = float(bot.price_feed.get_price(ticker))
            proposed = float(limit_price)
        except Exception:
            return decision
        if live_price <= 0 or proposed <= 0:
            return decision

        drift_pct = abs(proposed - live_price) / live_price
        if drift_pct <= 0.05:
            return decision

        reasoning = (
            f"{getattr(decision, 'reasoning', '')} | "
            f"Execution guard: stale limit ${proposed:.2f} refreshed near live price ${live_price:.2f}"
        ).strip()
        logger.info(
            "[%s] Refreshed stale %s limit for %s from %.2f to marketable live price %.2f",
            bot.name,
            action,
            ticker,
            proposed,
            live_price,
        )
        return self._copy_decision(decision, limit_price=None, reasoning=reasoning)

    def _autosize_order(self, bot, decision: OrderDecision) -> OrderDecision:
        action = str(getattr(decision, "action", "") or "").upper()
        ticker = getattr(decision, "ticker", None)
        if action not in {"BUY", "SELL"} or not ticker:
            return decision

        try:
            requested_qty = int(getattr(decision, "quantity", 0) or 0)
        except Exception:
            return decision
        if requested_qty <= 0:
            return decision

        try:
            price = (
                float(decision.limit_price)
                if getattr(decision, "limit_price", None) is not None
                else float(bot.price_feed.get_price(ticker))
            )
        except Exception:
            return decision
        if price <= 0:
            return decision

        snapshot = bot.portfolio.snapshot()
        cash = float(snapshot.get("cash", 0.0))
        current_qty = int((snapshot.get("positions") or {}).get(str(ticker).upper(), 0))
        caps = [
            int(self._risk_limits.max_order_quantity),
            int(self._risk_limits.max_order_notional // price),
        ]

        if action == "BUY":
            spendable = max(0.0, cash - float(self._risk_limits.min_cash_after_buy))
            remaining_position_qty = max(0, int(self._risk_limits.max_position_quantity) - current_qty)
            remaining_position_notional = max(
                0.0,
                float(self._risk_limits.max_position_notional) - current_qty * price,
            )
            caps.extend([
                int(spendable // price),
                remaining_position_qty,
                int(remaining_position_notional // price),
            ])
        elif not self._risk_limits.allow_short_selling:
            caps.append(max(0, current_qty))

        allowed_qty = min(caps)
        if allowed_qty <= 0 or allowed_qty >= requested_qty:
            return decision

        reasoning = (
            f"{getattr(decision, 'reasoning', '')} | "
            f"Risk auto-sized quantity from {requested_qty} to {allowed_qty}"
        ).strip()
        logger.info(
            "[%s] Auto-sized %s %s from %s to %s shares at estimated %.2f",
            bot.name,
            action,
            ticker,
            requested_qty,
            allowed_qty,
            price,
        )
        return self._copy_decision(decision, quantity=allowed_qty, reasoning=reasoning)

    @staticmethod
    def _copy_decision(decision: OrderDecision, **changes) -> OrderDecision:
        data = {
            "action": getattr(decision, "action", None),
            "ticker": getattr(decision, "ticker", None),
            "quantity": getattr(decision, "quantity", None),
            "limit_price": getattr(decision, "limit_price", None),
            "reasoning": getattr(decision, "reasoning", ""),
            "headline_used": getattr(decision, "headline_used", None),
            "confidence": getattr(decision, "confidence", None),
            "evidence_ids": list(getattr(decision, "evidence_ids", []) or []),
            "evidence_urls": list(getattr(decision, "evidence_urls", []) or []),
            "research_tickers": list(getattr(decision, "research_tickers", []) or []),
            "llm_call_made": bool(getattr(decision, "llm_call_made", True)),
            "speculative": bool(getattr(decision, "speculative", False)),
        }
        data.update(changes)
        return OrderDecision(**data)

    @staticmethod
    def _risk_rejection_decision(decision, risk_result) -> OrderDecision:
        original = (
            f"{decision.action} {decision.quantity} {decision.ticker}"
            if getattr(decision, "ticker", None)
            else str(getattr(decision, "action", "UNKNOWN"))
        )
        reasoning = (
            f"{getattr(decision, 'reasoning', '')} | "
            f"Risk check rejected original order ({original}): {risk_result.reason}"
        ).strip()
        return OrderDecision(
            action="HOLD",
            ticker=None,
            quantity=None,
            limit_price=None,
            reasoning=reasoning,
            headline_used=getattr(decision, "headline_used", None),
            confidence=getattr(decision, "confidence", None),
            evidence_ids=list(getattr(decision, "evidence_ids", []) or []),
            evidence_urls=list(getattr(decision, "evidence_urls", []) or []),
            research_tickers=list(getattr(decision, "research_tickers", []) or []),
            llm_call_made=bool(getattr(decision, "llm_call_made", True)),
            speculative=bool(getattr(decision, "speculative", False)),
        )
