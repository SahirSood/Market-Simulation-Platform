"""Read-only configuration endpoints."""
from fastapi import APIRouter

from api import state as app_state
from api.dependencies import public_read_only_mode_enabled
from model_config import bot_model_metadata, model_registry
from risk import RiskLimits

router = APIRouter()


def _risk_limits_from_state(state) -> RiskLimits:
    risk_limits = getattr(state, "risk_limits", None)
    if risk_limits is not None:
        return risk_limits
    scheduler = getattr(state, "scheduler", None)
    risk_limits = getattr(scheduler, "_risk_limits", None)
    return risk_limits or RiskLimits()


@router.get("/config/models")
async def get_model_config():
    """Configured model, prompt, RAG, and live bot metadata."""
    state = app_state.get()
    risk_limits = _risk_limits_from_state(state)
    payload = {
        **model_registry(),
        "live_bots": [
            bot_model_metadata(bot, risk_limits=risk_limits)
            for bot in getattr(state, "bots", []) or []
        ],
    }
    if public_read_only_mode_enabled():
        return _public_model_config(payload)
    return payload


@router.get("/config/risk-limits")
async def get_risk_limits():
    """Current deterministic risk limits used before engine submission."""
    state = app_state.get()
    return {"risk_limits": _risk_limits_from_state(state).to_dict()}


def _public_model_config(payload: dict) -> dict:
    """Return showcase metadata without operator-only configuration details."""
    cost_controls = dict(payload.get("cost_controls") or {})
    live_controls = dict(payload.get("live_controls") or {})
    trading = dict(payload.get("trading") or {})
    rag = dict(payload.get("rag") or {})
    return {
        "public_read_only": True,
        "prompt_version": payload.get("prompt_version"),
        "providers": payload.get("providers") or {},
        "starting_cash": payload.get("starting_cash"),
        "trading": {
            "tradable_tickers": trading.get("tradable_tickers") or [],
            "short_selling_enabled": bool(trading.get("short_selling_enabled")),
        },
        "live_controls": {
            "market_hours_only": live_controls.get("market_hours_only"),
            "market_timezone": live_controls.get("market_timezone"),
            "market_open_time": live_controls.get("market_open_time"),
            "market_close_time": live_controls.get("market_close_time"),
        },
        "cost_controls": {
            "llm_cost_guard_enabled": cost_controls.get("llm_cost_guard_enabled"),
            "llm_monthly_spend_limit_usd": cost_controls.get("llm_monthly_spend_limit_usd"),
            "llm_daily_spend_limit_usd": cost_controls.get("llm_daily_spend_limit_usd"),
        },
        "rag": {
            "top_k": rag.get("top_k"),
            "min_evidence_score": rag.get("min_evidence_score"),
        },
        "live_bots": [
            {
                "mode": row.get("mode"),
                "bot_id": row.get("bot_id"),
                "bot_name": row.get("bot_name"),
                "base_personality": row.get("base_personality"),
                "provider": row.get("provider"),
                "model": row.get("model"),
                "prompt_version": row.get("prompt_version"),
            }
            for row in payload.get("live_bots", []) or []
        ],
    }
