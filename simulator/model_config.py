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
    OPENAI_MODEL,
    PROMPT_VERSION,
    RAG_MIN_EVIDENCE_SCORE,
    RAG_TOP_K,
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


def _risk_limits_dict(risk_limits: Optional[RiskLimits | dict]) -> dict:
    if isinstance(risk_limits, dict):
        return dict(risk_limits)
    if risk_limits is not None and hasattr(risk_limits, "to_dict"):
        value = risk_limits.to_dict()
        if isinstance(value, dict):
            return value
    return RiskLimits().to_dict()
