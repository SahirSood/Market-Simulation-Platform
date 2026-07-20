"""Model, prompt, and run-configuration metadata helpers.

The values here are plain dictionaries so they can be stored in SQLAlchemy JSON
columns, replay configs, API responses, and comparison reports.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Iterable, Optional

from config import (
    CLAUDE_MODEL,
    EMBEDDING_MODEL,
    EVIDENCE_QUERY_HEADLINE_LIMIT,
    LLM_CLAUDE_DAILY_CALL_BUDGET,
    LLM_CLAUDE_MONTHLY_CALL_BUDGET,
    LLM_MAX_TOKENS,
    LLM_COST_GUARD_ENABLED,
    LLM_DAILY_DECISION_BUDGET,
    LLM_MONTHLY_DECISION_BUDGET,
    LLM_OPENAI_DAILY_CALL_BUDGET,
    LLM_OPENAI_MONTHLY_CALL_BUDGET,
    LLM_PROMPT_CACHE_ENABLED,
    LLM_SKIP_UNCHANGED_PROMPTS,
    MARKET_CLOSE_TIME,
    MARKET_HOURS_ONLY,
    MARKET_OPEN_TIME,
    MARKET_TIMEZONE,
    OPENAI_MODEL,
    PROMPT_VERSION,
    PROMPT_EVIDENCE_CHARS,
    PROMPT_EVIDENCE_LIMIT,
    PROMPT_RECENT_LIMIT,
    PROMPT_TICKER_HEADLINE_LIMIT,
    PROMPT_TICKER_LIMIT,
    PROMPT_TRENDING_LIMIT,
    RAG_MIN_EVIDENCE_SCORE,
    RAG_TOP_K,
    RESEARCH_AUTO_INGEST_ENABLED,
    RESEARCH_EXPAND_TRADABLE_UNIVERSE,
    RESEARCH_FORMS,
    RESEARCH_MAX_TICKERS_PER_DAY,
    RESEARCH_TICKER_COOLDOWN_MINS,
    SEED_LIQUIDITY_LEVELS,
    SEED_LIQUIDITY_ON_STARTUP,
    SEED_LIQUIDITY_QTY,
    SEED_LIQUIDITY_SPREAD_PCT,
    STARTING_CASH,
    TRADABLE_TICKERS,
)
from risk import RiskLimits


def prompt_hash(prompt: str | None) -> str | None:
    if not isinstance(prompt, str):
        return None
    return sha256(prompt.encode("utf-8")).hexdigest()


def provider_model(provider: str | None) -> str | None:
    provider_key = str(provider or "").lower()
    if provider_key == "claude":
        return CLAUDE_MODEL
    if provider_key == "openai":
        return OPENAI_MODEL
    return None


def base_personality(bot_name: str | None) -> str | None:
    if not bot_name:
        return None
    return str(bot_name).split(" (", 1)[0]


def bot_model_metadata(
    bot,
    risk_limits: Optional[RiskLimits | dict] = None,
    mode: str = "live",
) -> dict:
    """Return reproducibility metadata for one bot decision stream."""
    provider = getattr(bot, "llm_provider", None)
    prompt = getattr(bot, "personality_prompt", None)
    return {
        "mode": mode,
        "bot_id": getattr(bot, "bot_id", None),
        "bot_name": getattr(bot, "name", None),
        "base_personality": base_personality(getattr(bot, "name", None)),
        "provider": provider,
        "model": provider_model(provider),
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(prompt),
        "cost_controls": prompt_cost_controls(),
        "rag": {
            "top_k": RAG_TOP_K,
            "min_evidence_score": RAG_MIN_EVIDENCE_SCORE,
            "embedding_model": EMBEDDING_MODEL,
        },
        "tool_mode_enabled": bool(getattr(bot, "use_agent_tools", False)),
        "risk_limits": _risk_limits_dict(risk_limits),
    }


def model_registry() -> dict:
    """Return configured model defaults without requiring live bot instances."""
    return {
        "prompt_version": PROMPT_VERSION,
        "providers": {
            "claude": {"model": CLAUDE_MODEL},
            "openai": {"model": OPENAI_MODEL},
        },
        "starting_cash": STARTING_CASH,
        "trading": trading_config(),
        "live_controls": live_controls(),
        "cost_controls": prompt_cost_controls(),
        "rag": {
            "top_k": RAG_TOP_K,
            "min_evidence_score": RAG_MIN_EVIDENCE_SCORE,
            "embedding_model": EMBEDDING_MODEL,
        },
    }


def replay_config_snapshot(
    bots: Iterable | None = None,
    providers: Iterable[str] | None = None,
    risk_limits: Optional[RiskLimits | dict] = None,
) -> dict:
    """Snapshot model/prompt config for replay run metadata."""
    bot_rows = [
        bot_model_metadata(bot, risk_limits=risk_limits, mode="replay")
        for bot in (bots or [])
    ]
    return {
        **model_registry(),
        "providers_requested": list(providers or []),
        "bots": bot_rows,
        "risk_limits": _risk_limits_dict(risk_limits),
    }


def trading_config() -> dict:
    return {
        "tradable_tickers": list(TRADABLE_TICKERS),
        "seed_liquidity_on_startup": SEED_LIQUIDITY_ON_STARTUP,
        "seed_liquidity_levels": SEED_LIQUIDITY_LEVELS,
        "seed_liquidity_qty": SEED_LIQUIDITY_QTY,
        "seed_liquidity_spread_pct": SEED_LIQUIDITY_SPREAD_PCT,
    }


def live_controls() -> dict:
    return {
        "market_hours_only": MARKET_HOURS_ONLY,
        "market_timezone": MARKET_TIMEZONE,
        "market_open_time": MARKET_OPEN_TIME,
        "market_close_time": MARKET_CLOSE_TIME,
        "research_auto_ingest_enabled": RESEARCH_AUTO_INGEST_ENABLED,
        "research_forms": list(RESEARCH_FORMS),
        "research_max_tickers_per_day": RESEARCH_MAX_TICKERS_PER_DAY,
        "research_ticker_cooldown_mins": RESEARCH_TICKER_COOLDOWN_MINS,
        "research_expand_tradable_universe": RESEARCH_EXPAND_TRADABLE_UNIVERSE,
        "llm_cost_guard_enabled": LLM_COST_GUARD_ENABLED,
        "llm_daily_decision_budget": LLM_DAILY_DECISION_BUDGET,
        "llm_monthly_decision_budget": LLM_MONTHLY_DECISION_BUDGET,
        "llm_provider_budgets": {
            "claude": {
                "daily_call_budget": LLM_CLAUDE_DAILY_CALL_BUDGET,
                "monthly_call_budget": LLM_CLAUDE_MONTHLY_CALL_BUDGET,
            },
            "openai": {
                "daily_call_budget": LLM_OPENAI_DAILY_CALL_BUDGET,
                "monthly_call_budget": LLM_OPENAI_MONTHLY_CALL_BUDGET,
            },
        },
    }


def prompt_cost_controls() -> dict:
    return {
        "llm_max_tokens": LLM_MAX_TOKENS,
        "llm_prompt_cache_enabled": LLM_PROMPT_CACHE_ENABLED,
        "llm_skip_unchanged_prompts": LLM_SKIP_UNCHANGED_PROMPTS,
        "llm_cost_guard_enabled": LLM_COST_GUARD_ENABLED,
        "llm_daily_decision_budget": LLM_DAILY_DECISION_BUDGET,
        "llm_monthly_decision_budget": LLM_MONTHLY_DECISION_BUDGET,
        "llm_provider_budgets": {
            "claude": {
                "daily_call_budget": LLM_CLAUDE_DAILY_CALL_BUDGET,
                "monthly_call_budget": LLM_CLAUDE_MONTHLY_CALL_BUDGET,
            },
            "openai": {
                "daily_call_budget": LLM_OPENAI_DAILY_CALL_BUDGET,
                "monthly_call_budget": LLM_OPENAI_MONTHLY_CALL_BUDGET,
            },
        },
        "prompt_trending_limit": PROMPT_TRENDING_LIMIT,
        "prompt_recent_limit": PROMPT_RECENT_LIMIT,
        "prompt_ticker_limit": PROMPT_TICKER_LIMIT,
        "prompt_ticker_headline_limit": PROMPT_TICKER_HEADLINE_LIMIT,
        "prompt_evidence_limit": PROMPT_EVIDENCE_LIMIT,
        "prompt_evidence_chars": PROMPT_EVIDENCE_CHARS,
        "evidence_query_headline_limit": EVIDENCE_QUERY_HEADLINE_LIMIT,
    }


def _risk_limits_dict(risk_limits: Optional[RiskLimits | dict]) -> dict:
    if isinstance(risk_limits, dict):
        return dict(risk_limits)
    if risk_limits is not None and hasattr(risk_limits, "to_dict"):
        value = risk_limits.to_dict()
        if isinstance(value, dict):
            return value
    return RiskLimits().to_dict()
