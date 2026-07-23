import logging

from base_bot import BaseBot, OrderDecision

logger = logging.getLogger(__name__)

_PERSONALITY = """\
You are ContrarianBot. You do the opposite of what the crowd is doing.
When markets are surging, you sell. When they are crashing, you buy.
You look for crowded trades and fade them. Buy when others are fearful, sell when greedy.
If prices have moved more than 1% intraday in one direction, bet on the reversal.
Use limit orders. Quantity: 25–100 shares."""

# Intraday move threshold (%) that triggers a contrarian response
_FADE_THRESHOLD_PCT = 1.0

# Tickers ContrarianBot watches for intraday moves
_WATCH_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA", "SPY", "QQQ"]


class ContrarianBot(BaseBot):
    def __init__(
        self,
        price_feed,
        news_feed,
        llm_provider: str = "claude",
        rag_repository=None,
        embedding_service=None,
    ):
        super().__init__(
            bot_id="contrarian-001",
            name="ContrarianBot",
            personality_prompt=_PERSONALITY,
            price_feed=price_feed,
            news_feed=news_feed,
            llm_provider=llm_provider,
            rag_repository=rag_repository,
            embedding_service=embedding_service,
        )

    def _intraday_moves(self) -> list[str]:
        """
        Returns a list of human-readable strings describing significant intraday moves,
        e.g. ["AAPL is up 2.3% today", "NVDA is down 1.8% today"].
        These are injected into the prompt so the LLM has concrete numbers to fade.
        """
        lines = []
        for ticker in _WATCH_TICKERS:
            try:
                ohlcv = self.price_feed.get_ohlcv(ticker)
                price = self.price_feed.get_price(ticker)
                prev_close = ohlcv.get("close")
                if prev_close and prev_close > 0:
                    pct = (price - prev_close) / prev_close * 100
                    if abs(pct) >= _FADE_THRESHOLD_PCT:
                        direction = "up" if pct > 0 else "down"
                        lines.append(f"{ticker} is {direction} {abs(pct):.1f}% today")
            except Exception:
                pass
        return lines

    def _build_prompt(self, context: dict) -> str:
        """Override to inject intraday move data before the standard prompt."""
        moves = self._intraday_moves()
        base_prompt = super()._build_prompt(context)
        if moves:
            moves_str = "\n".join(f"  {m}" for m in moves)
            return f"INTRADAY MOVES (fade these):\n{moves_str}\n\n{base_prompt}"
        return base_prompt

    def decide(self) -> OrderDecision:
        context = self.get_context()
        prompt  = self._build_prompt(context)
        raw     = self._call_llm(prompt)

        if raw["action"] != "HOLD":
            # Enforce quantity bounds: 25–100
            qty = self._coerce_positive_int(raw.get("quantity"), default=50)
            raw["quantity"] = max(25, min(100, int(qty)))

        raw = self._apply_evidence_guardrail(raw)

        return OrderDecision(**self._finalize_decision_payload(raw))
