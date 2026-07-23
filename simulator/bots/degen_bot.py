import logging
import re

from base_bot import BaseBot, OrderDecision

logger = logging.getLogger(__name__)

_PERSONALITY = """\
You are DegenBot, a high-energy aggressive momentum trader. You chase price action.
You NEVER use limit orders — always market orders (set limit_price to null).
You trade on any positive OR negative headline — positive = BUY, negative = SELL.
You NEVER HOLD. If there is nothing to act on, pick BUY or SELL based on gut feeling.
Quantity should be aggressive: 50–200 shares. React fast, think later."""

_BULLISH_WORDS = {"rise", "rises", "gain", "gains", "up", "surge", "surges", "beat",
                  "beats", "record", "rally", "rallies", "strong", "growth", "boost",
                  "profit", "profits", "buy", "bullish", "high", "highs"}
_BEARISH_WORDS = {"fall", "falls", "drop", "drops", "down", "decline", "miss", "misses",
                  "loss", "losses", "weak", "cut", "sell", "bearish", "low", "lows",
                  "crash", "fear", "fears", "recession", "warning", "concern"}


def _sentiment(headlines: list[dict]) -> str:
    """Crude keyword scan: returns 'BUY' if bullish words outnumber bearish, else 'SELL'."""
    bull = bear = 0
    for h in headlines:
        words = h.get("title", "").lower().split()
        bull += sum(1 for w in words if w in _BULLISH_WORDS)
        bear += sum(1 for w in words if w in _BEARISH_WORDS)
    return "BUY" if bull >= bear else "SELL"


def _fallback_ticker(context: dict, raw: dict, normalize) -> str | None:
    ticker = normalize(raw.get("ticker"))
    tradable = [normalize(t) for t in (context.get("tradable_tickers") or [])]
    tradable = [candidate for candidate in tradable if candidate]
    allowed = set(tradable)
    if ticker and (not allowed or ticker in allowed):
        return ticker

    text_parts = [raw.get("headline_used") or ""]
    text_parts.extend(h.get("title", "") for h in context.get("trending_headlines", []) or [])
    text_parts.extend(h.get("title", "") for h in context.get("recent_headlines", []) or [])
    text = " ".join(text_parts).upper()
    for candidate in tradable:
        if re.search(rf"(?<![A-Z0-9]){re.escape(candidate)}(?![A-Z0-9])", text):
            return candidate
    return tradable[0] if tradable else ticker


class DegenBot(BaseBot):
    def __init__(
        self,
        price_feed,
        news_feed,
        llm_provider: str = "claude",
        rag_repository=None,
        embedding_service=None,
    ):
        super().__init__(
            bot_id="degen-001",
            name="DegenBot",
            personality_prompt=_PERSONALITY,
            price_feed=price_feed,
            news_feed=news_feed,
            llm_provider=llm_provider,
            rag_repository=rag_repository,
            embedding_service=embedding_service,
        )

    def decide(self) -> OrderDecision:
        context = self.get_context()
        prompt  = self._build_prompt(context)
        raw     = self._call_llm(prompt)

        # Degen always uses market orders
        raw["limit_price"] = None

        # Degen never holds — flip to sentiment-driven trade
        if raw["action"] == "HOLD" and raw.get("llm_call_made", True):
            all_headlines = context["trending_headlines"] + context["recent_headlines"]
            raw["action"] = _sentiment(all_headlines)
            raw["ticker"] = _fallback_ticker(context, raw, self._normalize_ticker)
            logger.debug(f"[DegenBot] LLM returned HOLD — flipped to {raw['action']} via sentiment")

        # Enforce quantity bounds: 50–200
        if raw["action"] != "HOLD":
            qty = self._coerce_positive_int(raw.get("quantity"), default=100)
            raw["quantity"] = max(50, min(200, int(qty)))
            raw["speculative"] = True

        raw = self._apply_evidence_guardrail(raw)

        return OrderDecision(**self._finalize_decision_payload(raw))
