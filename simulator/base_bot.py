import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import anthropic
import openai

from config import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    CLAUDE_MODEL,
    OPENAI_MODEL,
    STARTING_CASH,
)
from portfolio import Portfolio

logger = logging.getLogger(__name__)

_HOLD_FALLBACK = {
    "action": "HOLD",
    "ticker": None,
    "quantity": None,
    "limit_price": None,
    "reasoning": "LLM call failed - defaulting to HOLD",
    "headline_used": None,
}

_JSON_FORMAT_INSTRUCTIONS = """
Reply ONLY with valid JSON, no other text, no markdown:
{
  "action": "BUY" or "SELL" or "HOLD",
  "ticker": "SYMBOL" or null,
  "quantity": integer or null,
  "limit_price": float or null,
  "reasoning": "one sentence",
  "headline_used": "the headline that drove this decision" or null
}"""


@dataclass
class OrderDecision:
    action: str
    ticker: str | None
    quantity: int | None
    limit_price: float | None
    reasoning: str
    headline_used: str | None


class BaseBot(ABC):
    def __init__(
        self,
        bot_id: str,
        name: str,
        personality_prompt: str,
        price_feed,
        news_feed,
        llm_provider: str = "claude",
    ):
        self.bot_id = bot_id
        self.name = name
        self.personality_prompt = personality_prompt
        self.price_feed = price_feed
        self.news_feed = news_feed
        self.llm_provider = llm_provider.lower()
        self.portfolio = Portfolio(STARTING_CASH)

        # Create the provider client once so decision calls stay lightweight.
        if self.llm_provider == "claude":
            self._claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        elif self.llm_provider == "openai":
            self._openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        else:
            raise ValueError(
                f"Unknown llm_provider '{llm_provider}'. Use 'claude' or 'openai'."
            )

    @property
    def cash(self) -> float:
        return self.portfolio.cash

    @property
    def positions(self) -> dict:
        return self.portfolio.positions

    @abstractmethod
    def decide(self) -> OrderDecision:
        """Subclasses implement their personality-specific decision logic here."""

    def get_context(self) -> dict:
        """
        Builds the data packet handed to every bot before it decides.
        Includes both trending and recent headlines so bots can weight by recency.
        """
        return {
            "trending_headlines": self.news_feed.get_trending(),
            "recent_headlines": self.news_feed.get_recent(),
            "positions": self.positions,
            "cash": self.cash,
            "total_positions": len(self.positions),
        }

    def _build_prompt(self, context: dict) -> str:
        """Assembles the user-turn prompt from context dict + JSON instructions."""
        trending = context.get("trending_headlines", [])
        recent = context.get("recent_headlines", [])

        def fmt(headlines: list[dict]) -> str:
            if not headlines:
                return "  (none)"
            return "\n".join(
                f"  [{h['age_label']}] [{h['source']}] {h['title']}"
                for h in headlines
            )

        positions_str = (
            "\n".join(
                f"  {ticker}: {qty} shares"
                for ticker, qty in context["positions"].items()
            )
            or "  (none)"
        )

        prompt = f"""
TRENDING HEADLINES (high engagement):
{fmt(trending)}

RECENT HEADLINES (newest first):
{fmt(recent)}

YOUR PORTFOLIO:
  Cash available: ${context['cash']:,.2f}
  Open positions:
{positions_str}

Based on the above, make ONE trading decision.
{_JSON_FORMAT_INSTRUCTIONS}"""
        return prompt.strip()

    def _call_llm(self, prompt: str) -> dict:
        """
        Call the configured LLM (Claude or OpenAI) and return parsed JSON.
        Any failure returns HOLD so the trading loop stays alive.
        """
        try:
            if self.llm_provider == "claude":
                response = self._claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=256,
                    system=self.personality_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = response.content[0].text
            else:
                response = self._openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    max_tokens=256,
                    messages=[
                        {"role": "system", "content": self.personality_prompt},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = response.choices[0].message.content

            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw)

            required = {
                "action",
                "ticker",
                "quantity",
                "limit_price",
                "reasoning",
                "headline_used",
            }
            if not required.issubset(parsed.keys()):
                raise ValueError(f"LLM response missing fields: {required - parsed.keys()}")

            parsed["action"] = parsed["action"].upper()
            if parsed["action"] not in ("BUY", "SELL", "HOLD"):
                raise ValueError(f"Invalid action: {parsed['action']}")

            return parsed
        except Exception as e:
            logger.warning(f"[{self.name}] LLM call failed: {e}")
            return _HOLD_FALLBACK.copy()
