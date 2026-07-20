import logging
import time

from base_bot import BaseBot, OrderDecision
from config import ANALYST_AGENT_TOOLS_ENABLED

logger = logging.getLogger(__name__)

_PERSONALITY = """\
You are AnalystBot, a methodical data-driven trader. You only act on strong conviction.
You ALWAYS use limit orders - never market orders. Set a specific limit_price.
Bid prices should be 0.5% below the current price. Ask prices 0.5% above.
You trade at most once per hour. Quantity is modest: 10-50 shares.
When in doubt, HOLD. Only trade when the signal is overwhelming.
Explain your reasoning in detail."""

_COOLDOWN_SECS = 60 * 60


class AnalystBot(BaseBot):
    def __init__(
        self,
        price_feed,
        news_feed,
        llm_provider: str = "claude",
        rag_repository=None,
        embedding_service=None,
        agent_tool_server=None,
        use_agent_tools: bool | None = None,
    ):
        super().__init__(
            bot_id="analyst-001",
            name="AnalystBot",
            personality_prompt=_PERSONALITY,
            price_feed=price_feed,
            news_feed=news_feed,
            llm_provider=llm_provider,
            rag_repository=rag_repository,
            embedding_service=embedding_service,
        )
        self._last_trade_time: float = 0.0
        self.agent_tool_server = agent_tool_server
        self.use_agent_tools = (
            ANALYST_AGENT_TOOLS_ENABLED if use_agent_tools is None else use_agent_tools
        )

    def decide(self) -> OrderDecision:
        secs_since_trade = time.time() - self._last_trade_time
        if secs_since_trade < _COOLDOWN_SECS:
            remaining = int(_COOLDOWN_SECS - secs_since_trade)
            logger.info(f"[AnalystBot] Cooldown active - {remaining}s until next trade")
            return OrderDecision(
                action="HOLD",
                ticker=None,
                quantity=None,
                limit_price=None,
                reasoning=f"In cooldown - {remaining}s remaining before next trade",
                headline_used=None,
                confidence=0.0,
                evidence_ids=[],
                llm_call_made=False,
                speculative=False,
            )

        if self.use_agent_tools and self.agent_tool_server is not None:
            return self._decide_with_agent_tools()

        context = self.get_context()
        prompt = self._build_prompt(context)
        raw = self._call_llm(prompt)
        raw = self._normalize_trade(raw)
        raw = self._apply_evidence_guardrail(raw)

        if raw["action"] != "HOLD":
            self._last_trade_time = time.time()

        return OrderDecision(**raw)

    def _decide_with_agent_tools(self) -> OrderDecision:
        context = self.get_context()
        prompt = self._build_prompt(context)
        tool_context = self._build_agent_tool_context(context)
        raw = self._call_llm(f"{prompt}\n\nAGENT TOOL CONTEXT:\n{tool_context}")
        raw = self._normalize_trade(raw)
        raw = self._apply_evidence_guardrail(raw)
        raw = self._apply_agent_risk_preflight(raw)

        if raw["action"] != "HOLD":
            self._last_trade_time = time.time()

        return OrderDecision(**raw)

    def _normalize_trade(self, raw: dict) -> dict:
        if raw["action"] == "HOLD":
            return raw

        if raw["limit_price"] is None and raw["ticker"]:
            try:
                mid = self.price_feed.get_price(raw["ticker"])
                offset = mid * 0.005
                raw["limit_price"] = round(
                    mid - offset if raw["action"] == "BUY" else mid + offset,
                    2,
                )
                logger.debug(f"[AnalystBot] Derived limit_price={raw['limit_price']}")
            except Exception:
                pass

        qty = raw.get("quantity") or 25
        raw["quantity"] = max(10, min(50, int(qty)))
        return raw

    def _build_agent_tool_context(self, context: dict) -> str:
        ticker = self._evidence_ticker(context)
        query_text = self._evidence_query_text(context)
        sections = []
        tool_calls = [
            ("market_snapshot", {"ticker": ticker}),
            ("portfolio_snapshot", {"bot_id": self.bot_id}),
            ("retrieve_evidence", {"ticker": ticker, "query_text": query_text, "top_k": 3}),
            ("risk_limits", {}),
        ]
        for tool_name, args in tool_calls:
            try:
                result = self.agent_tool_server.call_tool(tool_name, args)
                sections.append(f"{tool_name}: {result}")
            except Exception as exc:
                sections.append(f"{tool_name}: unavailable ({exc})")
        return "\n".join(sections)

    def _apply_agent_risk_preflight(self, raw: dict) -> dict:
        if raw.get("action") == "HOLD":
            return raw

        try:
            result = self.agent_tool_server.call_tool(
                "risk_check_order",
                {
                    "bot_id": self.bot_id,
                    "action": raw.get("action"),
                    "ticker": raw.get("ticker"),
                    "quantity": raw.get("quantity"),
                    "limit_price": raw.get("limit_price"),
                },
            )
            risk = result.get("risk_check", {})
            if risk.get("approved", False):
                return raw
            raw["reasoning"] = (
                f"{raw.get('reasoning', '')} | Agent risk preflight rejected order: "
                f"{risk.get('reason')}"
            ).strip()
        except Exception as exc:
            raw["reasoning"] = (
                f"{raw.get('reasoning', '')} | Agent risk preflight unavailable: {exc}"
            ).strip()

        raw["action"] = "HOLD"
        raw["ticker"] = None
        raw["quantity"] = None
        raw["limit_price"] = None
        raw["confidence"] = 0.0
        return raw
