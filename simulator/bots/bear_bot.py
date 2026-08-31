import logging

from base_bot import BaseBot, OrderDecision

logger = logging.getLogger(__name__)

_PERSONALITY = """\
You are BearBot, a permanently pessimistic market participant.
You believe every rally is a dead-cat bounce and every positive headline is spin.
You interpret neutral news as quietly catastrophic. You almost always SELL or HOLD — never BUY.
When uncertain, sell. Find the bearish interpretation of every headline.
Prefer selling over buying. Conservative limit prices (set sell limits slightly below current price).
Typical position sizes: 50–150 shares."""


class BearBot(BaseBot):
    def __init__(
        self,
        price_feed,
        news_feed,
        llm_provider: str = "claude",
        rag_repository=None,
        embedding_service=None,
    ):
        super().__init__(
            bot_id="bear-001",
            name="BearBot",
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

        # Personality guardrail: BearBot is constitutionally incapable of buying
        if raw["action"] == "BUY":
            logger.warning("[BearBot] LLM returned BUY — overriding to HOLD per personality")
            raw["action"]      = "HOLD"
            raw["ticker"]      = None
            raw["quantity"]    = None
            raw["limit_price"] = None
            raw["hold_cause"]  = "guardrail"

        # A resting ask could leave the bear bots inactive for entire demos.
        # Use the deterministic risk gate plus a market sell for prompt action.
        if raw["action"] == "SELL":
            raw["limit_price"] = None

        raw = self._apply_evidence_guardrail(raw)

        return OrderDecision(**self._finalize_decision_payload(raw))
