import logging

from base_bot import BaseBot, OrderDecision

logger = logging.getLogger(__name__)

_PERSONALITY = """\
You are MacroBot. You ONLY care about big-picture macro events:
Federal Reserve decisions, interest rates, inflation (CPI, PCE, PPI),
GDP data, geopolitical events, currency moves, commodity prices, Treasury yields.
You completely ignore company-specific earnings, product launches, or personnel news.
If there are no macro headlines, you HOLD.
You only trade macro ETFs: SPY, QQQ, TLT, GLD, IEF.
Low frequency — hold positions for longer. Use limit orders."""

_MACRO_KEYWORDS = {
    "fed", "federal reserve", "fomc", "rate", "rates", "rate hike", "rate cut",
    "inflation", "cpi", "pce", "ppi", "gdp", "growth", "recession", "yield", "yields",
    "treasury", "bond", "bonds", "dollar", "currency", "forex", "oil", "gold",
    "commodity", "commodities", "geopolit", "war", "sanction", "tariff", "trade war",
    "interest", "monetary", "fiscal", "debt", "deficit", "unemployment", "jobs report",
    "nonfarm", "payroll", "macro",
}

_ALLOWED_TICKERS = {"SPY", "QQQ", "TLT", "GLD", "IEF"}


def _is_macro(headline: str) -> bool:
    lower = headline.lower()
    return any(kw in lower for kw in _MACRO_KEYWORDS)


class MacroBot(BaseBot):
    def __init__(self, price_feed, news_feed, llm_provider: str = "claude"):
        super().__init__(
            bot_id="macro-001",
            name="MacroBot",
            personality_prompt=_PERSONALITY,
            price_feed=price_feed,
            news_feed=news_feed,
            llm_provider=llm_provider,
        )

    def _filter_macro(self, headlines: list[dict]) -> list[dict]:
        return [h for h in headlines if _is_macro(h.get("title", ""))]

    def _build_prompt(self, context: dict) -> str:
        """Override: only pass macro headlines to the LLM."""
        macro_context = dict(context)
        macro_context["trending_headlines"] = self._filter_macro(
            context.get("trending_headlines", [])
        )
        macro_context["recent_headlines"] = self._filter_macro(
            context.get("recent_headlines", [])
        )
        return super()._build_prompt(macro_context)

    def decide(self) -> OrderDecision:
        context = self.get_context()

        # No macro headlines → HOLD without burning an LLM call
        all_headlines = context["trending_headlines"] + context["recent_headlines"]
        macro_headlines = self._filter_macro(all_headlines)
        if not macro_headlines:
            logger.info("[MacroBot] No macro headlines found — HOLD")
            return OrderDecision(
                action="HOLD", ticker=None, quantity=None, limit_price=None,
                reasoning="No macro-relevant headlines detected",
                headline_used=None,
            )

        prompt = self._build_prompt(context)
        raw    = self._call_llm(prompt)

        if raw["action"] != "HOLD":
            # Reject any ticker outside the allowed macro ETF universe
            if raw.get("ticker") not in _ALLOWED_TICKERS:
                logger.warning(
                    f"[MacroBot] LLM returned ticker={raw['ticker']} — "
                    f"not in allowed set {_ALLOWED_TICKERS}, overriding to HOLD"
                )
                raw["action"]      = "HOLD"
                raw["ticker"]      = None
                raw["quantity"]    = None
                raw["limit_price"] = None

        return OrderDecision(**raw)
