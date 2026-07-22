"""Small helpers for estimating LLM spend without logging prompt content."""
from __future__ import annotations

from typing import Any

from config import (
    LLM_CLAUDE_INPUT_COST_PER_1M_TOKENS,
    LLM_CLAUDE_OUTPUT_COST_PER_1M_TOKENS,
    LLM_ESTIMATED_INPUT_TOKENS_PER_CALL,
    LLM_ESTIMATED_OUTPUT_TOKENS_PER_CALL,
    LLM_FALLBACK_ESTIMATED_COST_PER_CALL_USD,
    LLM_OPENAI_INPUT_COST_PER_1M_TOKENS,
    LLM_OPENAI_OUTPUT_COST_PER_1M_TOKENS,
)


def extract_usage(provider: str, response: Any) -> dict:
    """Extract provider token usage from SDK responses when present."""
    key = str(provider or "").lower()
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    if key == "openai":
        input_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
        output_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
    else:
        input_tokens = _usage_value(usage, "input_tokens", "prompt_tokens")
        output_tokens = _usage_value(usage, "output_tokens", "completion_tokens")

    total_tokens = _usage_value(usage, "total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "llm_input_tokens": input_tokens,
        "llm_output_tokens": output_tokens,
        "llm_total_tokens": total_tokens,
    }


def estimate_call_cost_usd(
    provider: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> float:
    """Estimate spend and keep a conservative per-call floor for budget checks."""
    input_rate, output_rate = _provider_rates(provider)
    usage_estimate = 0.0
    if input_tokens is not None:
        usage_estimate += max(0, int(input_tokens)) * input_rate / 1_000_000
    if output_tokens is not None:
        usage_estimate += max(0, int(output_tokens)) * output_rate / 1_000_000
    return round(max(usage_estimate, LLM_FALLBACK_ESTIMATED_COST_PER_CALL_USD), 6)


def projected_call_cost_usd(provider: str | None = None) -> float:
    return estimate_call_cost_usd(
        provider or "",
        input_tokens=LLM_ESTIMATED_INPUT_TOKENS_PER_CALL,
        output_tokens=LLM_ESTIMATED_OUTPUT_TOKENS_PER_CALL,
    )


def _provider_rates(provider: str) -> tuple[float, float]:
    key = str(provider or "").lower()
    if key == "openai":
        return LLM_OPENAI_INPUT_COST_PER_1M_TOKENS, LLM_OPENAI_OUTPUT_COST_PER_1M_TOKENS
    return LLM_CLAUDE_INPUT_COST_PER_1M_TOKENS, LLM_CLAUDE_OUTPUT_COST_PER_1M_TOKENS


def _usage_value(usage: Any, *names: str) -> int | None:
    for name in names:
        if usage is None:
            return None
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if value is None:
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return None
