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
    LLM_DAILY_SPEND_LIMIT_USD,
    LLM_MONTHLY_DECISION_BUDGET,
    LLM_MONTHLY_SPEND_LIMIT_USD,
    LLM_OPENAI_DAILY_CALL_BUDGET,
    LLM_OPENAI_MONTHLY_CALL_BUDGET,
    MARKET_CLOSE_TIME,
    MARKET_HOURS_ONLY,
    MARKET_OPEN_TIME,
    MARKET_TIMEZONE,
    NOISE_INTERVAL,
)
from base_bot import OrderDecision
from llm_costs import projected_call_cost_usd
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
                self._settle_passive_fills()
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
                decision_id = self._log_decision(bot, decision, fills=[])
                self._record_agent_activity(
                    bot=bot,
                    event_type="decision",
                    stage="decision",
                    status="held",
                    summary="Bot held; no order submitted",
                    decision_id=decision_id,
                    evidence_ids=getattr(decision, "evidence_ids", []),
                )
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
            self._record_agent_activity(
                bot=bot,
                event_type="risk",
                stage="risk_check",
                status="approved" if risk_result.approved else "rejected",
                summary=(
                    f"Risk check approved {decision.action} {decision.quantity} {decision.ticker}"
                    if risk_result.approved
                    else f"Risk check rejected: {risk_result.reason}"
                ),
                evidence_ids=getattr(decision, "evidence_ids", []),
                metadata={
                    "action": decision.action,
                    "ticker": decision.ticker,
                    "quantity": decision.quantity,
                    "estimated_price": getattr(risk_result, "estimated_price", None),
                    "estimated_notional": getattr(risk_result, "estimated_notional", None),
                },
            )
            if not risk_result.approved:
                logger.warning(
                    f"[{bot.name}] Risk rejected {decision.action} "
                    f"{decision.quantity} {decision.ticker}: {risk_result.reason}"
                )
                rejected_order = decision
                rejection_decision = self._risk_rejection_decision(decision, risk_result)
                decision_id = self._log_decision(bot, rejection_decision, fills=[])
                self._record_execution_order(
                    bot=bot,
                    decision=rejected_order,
                    engine_order_id=None,
                    order_type="LIMIT" if rejected_order.limit_price else "MARKET",
                    submitted_price=self._estimated_order_price(bot, rejected_order),
                    fills=[],
                    decision_id=decision_id,
                    status="REJECTED",
                    rejection_reason=risk_result.reason,
                )
                self._record_agent_activity(
                    bot=bot,
                    event_type="execution",
                    stage="order_rejected",
                    status="rejected",
                    summary=f"Order blocked before engine submission: {risk_result.reason}",
                    decision_id=decision_id,
                    evidence_ids=getattr(rejected_order, "evidence_ids", []),
                    metadata={
                        "action": rejected_order.action,
                        "ticker": rejected_order.ticker,
                        "quantity": rejected_order.quantity,
                    },
                )
                if self._event_callback:
                    self._event_callback({
                        "type":       "decision",
                        "bot_id":     bot.bot_id,
                        "bot_name":   bot.name,
                        "action":     "HOLD",
                        "ticker":     None,
                        "quantity":   None,
                        "fill_count": 0,
                        "reasoning":  rejection_decision.reasoning,
                        "timestamp":  datetime.now(timezone.utc).isoformat(),
                    })
                return

            order_type = "LIMIT" if decision.limit_price else "MARKET"
            price = (decision.limit_price
                     or bot.price_feed.get_price(decision.ticker))

            try:
                order_id, fills = self._engine_adapter.submit(
                    ticker=decision.ticker,
                    side=decision.action,
                    order_type=order_type,
                    price=price,
                    quantity=decision.quantity,
                    bot_id=bot.bot_id,
                )
            except Exception as submit_exc:
                decision_id = self._log_decision(bot, decision, fills=[])
                self._record_execution_order(
                    bot=bot,
                    decision=decision,
                    engine_order_id=None,
                    order_type=order_type,
                    submitted_price=price,
                    fills=[],
                    decision_id=decision_id,
                    status="ERROR",
                    rejection_reason=str(submit_exc),
                )
                self._record_agent_activity(
                    bot=bot,
                    event_type="execution",
                    stage="order_submit",
                    status="error",
                    summary="Engine submission failed",
                    decision_id=decision_id,
                    evidence_ids=getattr(decision, "evidence_ids", []),
                    metadata={
                        "action": decision.action,
                        "ticker": decision.ticker,
                        "quantity": decision.quantity,
                        "order_type": order_type,
                    },
                )
                raise

            for fill in fills:
                bot.portfolio.apply_fill(fill, strict=False)

            decision_id = self._log_decision(bot, decision, fills=fills)
            self._record_execution_order(
                bot=bot,
                decision=decision,
                engine_order_id=order_id,
                order_type=order_type,
                submitted_price=price,
                fills=fills,
                decision_id=decision_id,
            )
            self._settle_passive_fills()
            fill_qty_total = sum(int(getattr(fill, "quantity", 0) or 0) for fill in fills)
            execution_status = "open"
            if fill_qty_total:
                execution_status = (
                    "filled"
                    if fill_qty_total >= int(getattr(decision, "quantity", 0) or 0)
                    else "partial"
                )
            self._record_agent_activity(
                bot=bot,
                event_type="execution",
                stage="order_submit",
                status=execution_status,
                summary=(
                    f"Submitted {order_type} {decision.action} {decision.quantity} {decision.ticker}; "
                    f"{fill_qty_total} share(s) filled"
                ),
                decision_id=decision_id,
                evidence_ids=getattr(decision, "evidence_ids", []),
                metadata={
                    "action": decision.action,
                    "ticker": decision.ticker,
                    "quantity": decision.quantity,
                    "order_type": order_type,
                    "engine_order_id": order_id,
                    "fill_count": len(fills),
                    "fill_qty_total": fill_qty_total,
                },
            )

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

    def _settle_passive_fills(self) -> None:
        """Credit fills produced after a bot's limit order began resting."""
        drainer = getattr(self._engine_adapter, "drain_fills", None)
        if not callable(drainer):
            return

        for bot in self._bots:
            try:
                fills = drainer(bot.bot_id)
            except Exception as exc:
                logger.warning("[%s] Passive fill drain failed: %s", bot.name, exc)
                continue
            if not fills:
                continue

            for fill in fills:
                bot.portfolio.apply_fill(fill, strict=False)

            recorder = getattr(self._reasoning_log, "record_passive_fills", None)
            if callable(recorder):
                try:
                    recorder(bot, fills)
                except Exception as exc:
                    logger.warning("[%s] Passive fill ledger write failed: %s", bot.name, exc)

            fill_qty_total = sum(int(getattr(fill, "quantity", 0) or 0) for fill in fills)
            self._record_agent_activity(
                bot=bot,
                event_type="execution",
                stage="passive_fill",
                status="filled",
                summary=f"Resting order filled {fill_qty_total} share(s)",
                metadata={
                    "fill_count": len(fills),
                    "fill_qty_total": fill_qty_total,
                    "order_ids": sorted({int(fill.order_id) for fill in fills}),
                },
            )
            if self._event_callback:
                self._event_callback({
                    "type": "trade",
                    "bot_id": bot.bot_id,
                    "bot_name": bot.name,
                    "action": fills[-1].side,
                    "ticker": fills[-1].ticker,
                    "quantity": fill_qty_total,
                    "fill_count": len(fills),
                    "reasoning": "Resting limit order received a later fill.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    def _log_decision(self, bot, decision: OrderDecision, fills: list) -> int | None:
        if not self._reasoning_log:
            return None
        try:
            decision_id = self._reasoning_log.log(bot, decision, fills=fills)
        except Exception as exc:
            logger.warning("[%s] Decision log write failed: %s", bot.name, exc)
            return None
        if isinstance(decision_id, bool):
            return None
        if isinstance(decision_id, int):
            return decision_id
        if isinstance(decision_id, str) and decision_id.isdigit():
            return int(decision_id)
        return None

    def _record_execution_order(
        self,
        bot,
        decision: OrderDecision,
        engine_order_id: int | None,
        order_type: str | None,
        submitted_price: float | None,
        fills: list,
        decision_id: int | None = None,
        status: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        recorder = getattr(self._reasoning_log, "record_execution_order", None)
        if not callable(recorder):
            return
        try:
            recorder(
                bot=bot,
                decision=decision,
                engine_order_id=engine_order_id,
                order_type=order_type,
                submitted_price=submitted_price,
                fills=fills,
                decision_id=decision_id,
                status=status,
                rejection_reason=rejection_reason,
            )
        except Exception as exc:
            logger.warning("[%s] Execution ledger write failed: %s", bot.name, exc)

    def _record_agent_activity(
        self,
        *,
        bot,
        event_type: str,
        stage: str,
        status: str,
        summary: str,
        decision_id: int | None = None,
        evidence_ids: list | None = None,
        metadata: dict | None = None,
    ) -> None:
        recorder = getattr(self._reasoning_log, "record_agent_activity", None)
        if not callable(recorder):
            return
        try:
            recorder(
                bot=bot,
                event_type=event_type,
                stage=stage,
                status=status,
                summary=summary,
                decision_id=decision_id,
                evidence_ids=evidence_ids or [],
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.warning("[%s] Agent activity write failed: %s", bot.name, exc)

    @staticmethod
    def _estimated_order_price(bot, decision: OrderDecision) -> float | None:
        if getattr(decision, "limit_price", None) is not None:
            try:
                return float(decision.limit_price)
            except (TypeError, ValueError):
                return None
        ticker = getattr(decision, "ticker", None)
        if not ticker:
            return None
        try:
            return float(bot.price_feed.get_price(ticker))
        except Exception:
            return None

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
        projected_cost = projected_call_cost_usd(provider)
        if LLM_DAILY_SPEND_LIMIT_USD > 0:
            if self._estimated_llm_cost(day_start) + projected_cost > LLM_DAILY_SPEND_LIMIT_USD:
                return True
        if LLM_MONTHLY_SPEND_LIMIT_USD > 0:
            if self._estimated_llm_cost(month_start) + projected_cost > LLM_MONTHLY_SPEND_LIMIT_USD:
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

    def _estimated_llm_cost(self, since: datetime, llm_provider: str | None = None) -> float:
        summer = getattr(self._reasoning_log, "sum_estimated_llm_cost", None)
        if not callable(summer):
            return 0.0
        try:
            value = summer(since=since, llm_provider=llm_provider)
        except TypeError:
            try:
                value = summer(since=since)
            except Exception:
                return 0.0
        except Exception as exc:
            logger.warning("[BotScheduler] Cost budget sum failed: %s", exc)
            return 0.0
        if isinstance(value, (int, float)):
            return max(0.0, float(value))
        if isinstance(value, str):
            try:
                return max(0.0, float(value))
            except ValueError:
                return 0.0
        return 0.0

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
        daily_cost = self._estimated_llm_cost(day_start)
        monthly_cost = self._estimated_llm_cost(month_start)
        provider_budgets = {}
        for provider in ("claude", "openai"):
            limits = self._provider_budget_limits(provider)
            provider_daily = self._billable_decision_count(day_start, provider)
            provider_monthly = self._billable_decision_count(month_start, provider)
            provider_daily_cost = self._estimated_llm_cost(day_start, provider)
            provider_monthly_cost = self._estimated_llm_cost(month_start, provider)
            provider_budgets[provider] = {
                "daily_billable_calls": provider_daily,
                "monthly_billable_calls": provider_monthly,
                "daily_estimated_cost_usd": round(provider_daily_cost, 6),
                "monthly_estimated_cost_usd": round(provider_monthly_cost, 6),
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
            "daily_spend_limit_usd": LLM_DAILY_SPEND_LIMIT_USD,
            "monthly_spend_limit_usd": LLM_MONTHLY_SPEND_LIMIT_USD,
            "daily_estimated_llm_cost_usd": round(daily_cost, 6),
            "monthly_estimated_llm_cost_usd": round(monthly_cost, 6),
            "projected_next_call_cost_usd": round(projected_call_cost_usd(), 6),
            "provider_budgets": provider_budgets,
            "decision_budget_exhausted": self._decision_budget_exhausted(),
            "spend_budget_exhausted": (
                (LLM_DAILY_SPEND_LIMIT_USD > 0 and daily_cost + projected_call_cost_usd() > LLM_DAILY_SPEND_LIMIT_USD)
                or (LLM_MONTHLY_SPEND_LIMIT_USD > 0 and monthly_cost + projected_call_cost_usd() > LLM_MONTHLY_SPEND_LIMIT_USD)
            ),
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
        else:
            # A sell can close a long and continue into a short, but the final
            # signed position must stay inside both quantity and notional caps.
            max_short_by_quantity = current_qty + int(self._risk_limits.max_position_quantity)
            max_abs_position_by_notional = int(self._risk_limits.max_position_notional // price)
            max_short_by_notional = current_qty + max_abs_position_by_notional
            caps.extend([
                max(0, max_short_by_quantity),
                max(0, max_short_by_notional),
            ])

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
            "llm_input_tokens": getattr(decision, "llm_input_tokens", None),
            "llm_output_tokens": getattr(decision, "llm_output_tokens", None),
            "llm_total_tokens": getattr(decision, "llm_total_tokens", None),
            "llm_estimated_cost_usd": getattr(decision, "llm_estimated_cost_usd", None),
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
            llm_input_tokens=getattr(decision, "llm_input_tokens", None),
            llm_output_tokens=getattr(decision, "llm_output_tokens", None),
            llm_total_tokens=getattr(decision, "llm_total_tokens", None),
            llm_estimated_cost_usd=getattr(decision, "llm_estimated_cost_usd", None),
            speculative=bool(getattr(decision, "speculative", False)),
        )
