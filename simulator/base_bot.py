import json
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256

try:
    import anthropic
except Exception:  # pragma: no cover - dependency may be optional in local tests
    anthropic = None

try:
    import openai
except Exception:  # pragma: no cover - dependency may be optional in local tests
    openai = None

from config import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    OPENAI_PROJECT_ID,
    CLAUDE_MODEL,
    EVIDENCE_QUERY_HEADLINE_LIMIT,
    LLM_MAX_TOKENS,
    LLM_PROMPT_CACHE_ENABLED,
    OPENAI_MODEL,
    STARTING_CASH,
    PROMPT_EVIDENCE_CHARS,
    PROMPT_EVIDENCE_LIMIT,
    PROMPT_RECENT_LIMIT,
    PROMPT_TICKER_HEADLINE_LIMIT,
    PROMPT_TICKER_LIMIT,
    PROMPT_TRENDING_LIMIT,
    RAG_TOP_K,
    RAG_MIN_EVIDENCE_SCORE,
    TRADABLE_TICKERS,
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
    "confidence": 0.0,
    "evidence_ids": [],
    "speculative": False,
}

_JSON_FORMAT_INSTRUCTIONS = """
Reply ONLY with valid JSON, no other text, no markdown:
{
  "action": "BUY" or "SELL" or "HOLD",
  "ticker": "SYMBOL" or null,
  "quantity": integer or null,
  "limit_price": float or null,
  "reasoning": "one sentence",
    "headline_used": "the headline that drove this decision" or null,
    "confidence": number from 0.0 to 1.0,
    "evidence_ids": [integer chunk ids used for this decision],
    "speculative": true or false
}"""


@dataclass
class OrderDecision:
    action: str
    ticker: str | None
    quantity: int | None
    limit_price: float | None
    reasoning: str
    headline_used: str | None
    confidence: float | None = None
    evidence_ids: list[int] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    speculative: bool = False


class BaseBot(ABC):
    def __init__(
        self,
        bot_id: str,
        name: str,
        personality_prompt: str,
        price_feed,
        news_feed,
        llm_provider: str = "claude",
        rag_repository=None,
        embedding_service=None,
    ):
        self.bot_id = bot_id
        self.name = name
        self.personality_prompt = personality_prompt
        self.price_feed = price_feed
        self.news_feed = news_feed
        self.llm_provider = llm_provider.lower()
        self.rag_repository = rag_repository
        self.embedding_service = embedding_service
        self.portfolio = Portfolio(STARTING_CASH)
        self._last_retrieved_evidence: list[dict] = []
        self._last_llm_prompt_hash: str | None = None
        self._last_llm_response: dict | None = None

        # Create the provider client once so decision calls stay lightweight.
        if self.llm_provider == "claude":
            self._claude_client = (
                anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                if anthropic is not None and ANTHROPIC_API_KEY
                else None
            )
            if self._claude_client is None:
                logger.warning(
                    f"[{self.name}] Anthropic client unavailable; decisions will fallback to HOLD unless _call_llm is mocked"
                )
        elif self.llm_provider == "openai":
            self._openai_client = (
                openai.OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT_ID)
                if openai is not None and OPENAI_API_KEY
                else None
            )
            if self._openai_client is None:
                logger.warning(
                    f"[{self.name}] OpenAI client unavailable; decisions will fallback to HOLD unless _call_llm is mocked"
                )
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

    def _get_limited_headlines(self, method_name: str, limit: int) -> list[dict]:
        method = getattr(self.news_feed, method_name, None)
        if not callable(method) or limit <= 0:
            return []
        try:
            rows = method(n=limit)
        except TypeError:
            rows = method()
        return list(rows or [])[:limit]

    def _get_limited_ticker_headlines(self, ticker: str) -> list[dict]:
        get_latest = getattr(self.news_feed, "get_latest", None)
        if not callable(get_latest) or PROMPT_TICKER_HEADLINE_LIMIT <= 0:
            return []
        try:
            rows = get_latest(ticker, n=PROMPT_TICKER_HEADLINE_LIMIT)
        except TypeError:
            rows = get_latest(ticker)
        return list(rows or [])[:PROMPT_TICKER_HEADLINE_LIMIT]

    def _get_tradable_tickers(self) -> list[str]:
        get_tradable = getattr(self.price_feed, "get_tradable_tickers", None)
        if callable(get_tradable):
            tickers = get_tradable()
        else:
            tickers = TRADABLE_TICKERS
        return [str(t).upper().strip() for t in tickers if str(t).strip()]

    def get_context(self) -> dict:
        """
        Builds the data packet handed to every bot before it decides.
        Includes both trending and recent headlines so bots can weight by recency.
        """
        ticker_headlines: dict[str, list[dict]] = {}
        get_active_tickers = getattr(self.price_feed, "get_active_tickers", None)

        if PROMPT_TICKER_LIMIT > 0:
            watchlist: list[str] = []
            watchlist.extend(self.positions.keys())
            if callable(get_active_tickers):
                watchlist.extend(get_active_tickers())

            # Keep prompt size and NewsAPI usage bounded.
            seen: set[str] = set()
            for ticker in watchlist:
                symbol = str(ticker).upper().strip()
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                headlines = self._get_limited_ticker_headlines(symbol)
                if headlines:
                    ticker_headlines[symbol] = headlines
                if len(ticker_headlines) >= PROMPT_TICKER_LIMIT:
                    break

        return {
            "trending_headlines": self._get_limited_headlines(
                "get_trending",
                PROMPT_TRENDING_LIMIT,
            ),
            "recent_headlines": self._get_limited_headlines(
                "get_recent",
                PROMPT_RECENT_LIMIT,
            ),
            "ticker_headlines": ticker_headlines,
            "tradable_tickers": self._get_tradable_tickers(),
            "positions": self.positions,
            "cash": self.cash,
            "total_positions": len(self.positions),
        }

    def _evidence_query_text(self, context: dict) -> str:
        parts: list[str] = []
        for h in context.get("trending_headlines", [])[:EVIDENCE_QUERY_HEADLINE_LIMIT]:
            if h.get("title"):
                parts.append(h["title"])
        for h in context.get("recent_headlines", [])[:EVIDENCE_QUERY_HEADLINE_LIMIT]:
            if h.get("title"):
                parts.append(h["title"])
        return " | ".join(parts)

    def _evidence_ticker(self, context: dict) -> str | None:
        ticker_map = context.get("ticker_headlines", {}) or {}
        if ticker_map:
            return next(iter(ticker_map.keys()))
        positions = context.get("positions", {}) or {}
        if positions:
            return next(iter(positions.keys()))
        return None

    def _retrieve_evidence(self, context: dict) -> list[dict]:
        if self.rag_repository is None:
            return []

        query_text = self._evidence_query_text(context)
        if not query_text:
            return []

        try:
            ticker = self._evidence_ticker(context)
            top_k = max(0, min(RAG_TOP_K, PROMPT_EVIDENCE_LIMIT))
            if top_k <= 0:
                return []
            rows = self.rag_repository.retrieve_evidence(
                ticker=ticker,
                query_text=query_text,
                top_k=top_k,
                embedding_service=self.embedding_service,
                as_of_date=context.get("as_of_date"),
            )
            if not rows and ticker:
                rows = self.rag_repository.retrieve_evidence(
                    ticker=None,
                    query_text=query_text,
                    top_k=top_k,
                    embedding_service=self.embedding_service,
                    as_of_date=context.get("as_of_date"),
                )
            return rows
        except Exception as e:
            logger.warning(f"[{self.name}] Evidence retrieval failed: {e}")
            return []

    def _format_evidence_for_prompt(self, evidence_rows: list[dict]) -> str:
        if not evidence_rows:
            return "  (no evidence retrieved)"

        lines = []
        for row in evidence_rows[:PROMPT_EVIDENCE_LIMIT]:
            snippet = (row.get("content") or "").strip().replace("\n", " ")
            if len(snippet) > PROMPT_EVIDENCE_CHARS:
                snippet = snippet[:PROMPT_EVIDENCE_CHARS] + "..."
            score = row.get("score")
            score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
            lines.append(
                f"  [chunk_id={row.get('chunk_id')}] [score={score_str}] "
                f"[source={self._evidence_source_label(row)}] {snippet}"
            )
        return "\n".join(lines)

    def _evidence_source_label(self, row: dict) -> str:
        pieces = [
            str(row.get("ticker") or "").upper().strip(),
            str(row.get("form_type") or row.get("source_type") or "").strip(),
        ]
        accession = str(row.get("accession_no") or "").strip()
        if accession:
            pieces.append(accession[-12:])
        label = "/".join(piece for piece in pieces if piece)
        return label or "unknown"

    def _build_prompt(self, context: dict) -> str:
        """Assembles the user-turn prompt from context dict + JSON instructions."""
        trending = context.get("trending_headlines", [])
        recent = context.get("recent_headlines", [])
        ticker_headlines = context.get("ticker_headlines", {})
        tradable_tickers = context.get("tradable_tickers", []) or self._get_tradable_tickers()
        evidence_rows = self._retrieve_evidence(context)
        self._last_retrieved_evidence = evidence_rows

        def fmt(headlines: list[dict]) -> str:
            if not headlines:
                return "  (none)"
            return "\n".join(
                f"  [{h['age_label']}] [{h['source']}] {h['title']}"
                for h in headlines
            )

        ticker_sections = []
        for ticker, headlines in ticker_headlines.items():
            ticker_sections.append(f"{ticker}:\n{fmt(headlines)}")
        ticker_news_str = "\n\n".join(ticker_sections) if ticker_sections else "  (none)"

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

TRADABLE TICKERS (choose ticker only from this list):
  {", ".join(tradable_tickers)}

TICKER-SPECIFIC HEADLINES:
{ticker_news_str}

YOUR PORTFOLIO:
  Cash available: ${context['cash']:,.2f}
  Open positions:
{positions_str}

RETRIEVED EVIDENCE (cite chunk_id values you actually used):
{self._format_evidence_for_prompt(evidence_rows)}

Based on the above, make ONE trading decision.
{_JSON_FORMAT_INSTRUCTIONS}"""
        return prompt.strip()

    def _apply_evidence_guardrail(self, raw: dict) -> dict:
        if self.rag_repository is None:
            # Keep prior behavior when RAG is not wired for this bot.
            raw.setdefault("confidence", 0.5 if raw.get("action") != "HOLD" else 0.0)
            raw.setdefault("evidence_ids", [])
            raw.setdefault("speculative", False)
            raw.setdefault("evidence_urls", [])
            return raw

        evidence_rows = self._last_retrieved_evidence or []
        raw.setdefault("confidence", 0.5 if raw.get("action") != "HOLD" else 0.0)
        raw.setdefault("evidence_ids", [])
        raw.setdefault("speculative", False)
        raw.setdefault("evidence_urls", [])

        if raw.get("action") == "HOLD":
            return raw

        strong_rows = [
            row for row in evidence_rows
            if isinstance(row.get("score"), (int, float))
            and row["score"] >= RAG_MIN_EVIDENCE_SCORE
        ]
        has_strong_evidence = bool(strong_rows)

        if not has_strong_evidence and not raw.get("speculative", False):
            raw["action"] = "HOLD"
            raw["ticker"] = None
            raw["quantity"] = None
            raw["limit_price"] = None
            raw["reasoning"] = (
                f"{raw.get('reasoning', '')} | Guardrail: no strong retrieved evidence; forced HOLD"
            ).strip()
            raw["confidence"] = 0.0
            raw["evidence_ids"] = []
            raw["evidence_urls"] = []
            return raw

        available = {int(r.get("chunk_id")) for r in evidence_rows if r.get("chunk_id") is not None}
        chosen_ids = []
        for value in raw.get("evidence_ids", []) or []:
            try:
                iv = int(value)
            except Exception:
                continue
            if iv in available:
                chosen_ids.append(iv)

        if not chosen_ids and strong_rows:
            chosen_ids = [int(strong_rows[0]["chunk_id"])]

        raw["evidence_ids"] = chosen_ids
        id_to_url = {
            int(r["chunk_id"]): r.get("source_url")
            for r in evidence_rows
            if r.get("chunk_id") is not None
        }
        raw["evidence_urls"] = [id_to_url[i] for i in chosen_ids if id_to_url.get(i)]
        return raw

    def _apply_tradable_universe_guardrail(self, raw: dict) -> dict:
        if raw.get("action") == "HOLD":
            return raw

        allowed = set(self._get_tradable_tickers())
        ticker = str(raw.get("ticker") or "").upper().strip()
        if not allowed or ticker in allowed:
            raw["ticker"] = ticker
            return raw

        raw["action"] = "HOLD"
        raw["ticker"] = None
        raw["quantity"] = None
        raw["limit_price"] = None
        raw["reasoning"] = (
            f"{raw.get('reasoning', '')} | Guardrail: ticker {ticker} is outside the tradable universe"
        ).strip()
        raw["confidence"] = 0.0
        raw["evidence_ids"] = []
        raw["evidence_urls"] = []
        return raw

    def _llm_prompt_cache_key(self, prompt: str) -> str:
        model = CLAUDE_MODEL if self.llm_provider == "claude" else OPENAI_MODEL
        payload = json.dumps(
            {
                "provider": self.llm_provider,
                "model": model,
                "system": self.personality_prompt,
                "prompt": prompt,
            },
            sort_keys=True,
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    def _call_llm(self, prompt: str) -> dict:
        """
        Call the configured LLM (Claude or OpenAI) and return parsed JSON.
        Any failure returns HOLD so the trading loop stays alive.
        """
        cache_key = self._llm_prompt_cache_key(prompt)
        if (
            LLM_PROMPT_CACHE_ENABLED
            and self._last_llm_prompt_hash == cache_key
            and self._last_llm_response is not None
        ):
            logger.info(f"[{self.name}] Reusing cached LLM decision for unchanged prompt")
            return deepcopy(self._last_llm_response)

        try:
            if self.llm_provider == "claude":
                if self._claude_client is None:
                    raise RuntimeError("Anthropic client not configured")
                response = self._claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=LLM_MAX_TOKENS,
                    system=self.personality_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = response.content[0].text
            else:
                if self._openai_client is None:
                    raise RuntimeError("OpenAI client not configured")
                response = self._openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    max_tokens=LLM_MAX_TOKENS,
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

            if "confidence" not in parsed:
                parsed["confidence"] = 0.5 if parsed["action"] != "HOLD" else 0.0
            try:
                parsed["confidence"] = float(parsed["confidence"])
            except Exception:
                parsed["confidence"] = 0.5 if parsed["action"] != "HOLD" else 0.0
            parsed["confidence"] = max(0.0, min(1.0, parsed["confidence"]))

            parsed["evidence_ids"] = parsed.get("evidence_ids") or []
            if not isinstance(parsed["evidence_ids"], list):
                parsed["evidence_ids"] = []

            parsed["speculative"] = bool(parsed.get("speculative", False))
            parsed = self._apply_tradable_universe_guardrail(parsed)

            if LLM_PROMPT_CACHE_ENABLED:
                self._last_llm_prompt_hash = cache_key
                self._last_llm_response = deepcopy(parsed)

            return parsed
        except Exception as e:
            logger.warning(f"[{self.name}] LLM call failed: {e}")
            return _HOLD_FALLBACK.copy()
