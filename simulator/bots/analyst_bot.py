import time
import logging

from base_bot import BaseBot, OrderDecision

logger = logging.getLogger(__name__)

_PERSONALITY = """\
You are AnalystBot, a methodical data-driven trader. You only act on strong conviction.
You ALWAYS use limit orders — never market orders. Set a specific limit_price.
Bid prices should be 0.5% below the current price. Ask prices 0.5% above.
You trade at most once per hour. Quantity is modest: 10–50 shares.
When in doubt, HOLD. Only trade when the signal is overwhelming.
Explain your reasoning in detail."""

# How long (seconds) before AnalystBot is willing to trade again
_COOLDOWN_SECS = 60 * 60  # 1 hour


class AnalystBot(BaseBot):
    def __init__(self, price_feed, news_feed, llm_provider: str = "claude"):
        super().__init__(
            bot_id="analyst-001",
            name="AnalystBot",
            personality_prompt=_PERSONALITY,
            price_feed=price_feed,
            news_feed=news_feed,
            llm_provider=llm_provider,
        )
        self._last_trade_time: float = 0.0

    def decide(self) -> OrderDecision:
        # Cooldown check — saves an LLM call when the bot recently traded
        secs_since_trade = time.time() - self._last_trade_time
        if secs_since_trade < _COOLDOWN_SECS:
            remaining = int(_COOLDOWN_SECS - secs_since_trade)
            logger.info(f"[AnalystBot] Cooldown active — {remaining}s until next trade")
            return OrderDecision(
                action="HOLD", ticker=None, quantity=None, limit_price=None,
                reasoning=f"In cooldown — {remaining}s remaining before next trade",
                headline_used=None,
            )

        context = self.get_context()
        prompt  = self._build_prompt(context)
        raw     = self._call_llm(prompt)

        if raw["action"] != "HOLD":
            # Enforce limit order: if LLM forgot to set a price, derive one
            if raw["limit_price"] is None and raw["ticker"]:
                try:
                    mid = self.price_feed.get_price(raw["ticker"])
                    offset = mid * 0.005  # 0.5%
                    raw["limit_price"] = round(
                        mid - offset if raw["action"] == "BUY" else mid + offset, 2
                    )
                    logger.debug(f"[AnalystBot] Derived limit_price={raw['limit_price']}")
                except Exception:
                    pass

            # Enforce quantity bounds: 10–50
            qty = raw.get("quantity") or 25
            raw["quantity"] = max(10, min(50, int(qty)))

            self._last_trade_time = time.time()

        return OrderDecision(**raw)
