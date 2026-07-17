"""
BotScheduler — orchestrates all agents on independent timers.

  - AI bots:       every BOT_CYCLE_MINS (20 min), staggered 60s apart
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

from config import BOT_CYCLE_MINS, NOISE_INTERVAL
from base_bot import OrderDecision
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
        risk_limits: Optional[RiskLimits] = None,
    ):
        self._bots            = bots
        self._noise_pool      = noise_pool
        self._engine_adapter  = engine_adapter
        self._reasoning_log   = reasoning_log
        self._event_callback  = event_callback
        self._bot_cycle_mins  = bot_cycle_mins
        self._noise_interval_secs = noise_interval_secs
        self._risk_limits = risk_limits or RiskLimits()
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
            self._schedule_bot(bot, delay=i * 60)

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
            self._noise_pool.tick()
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
            decision = bot.decide()

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
            speculative=bool(getattr(decision, "speculative", False)),
        )
