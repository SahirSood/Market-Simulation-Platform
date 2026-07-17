"""Read-only configuration endpoints."""
from fastapi import APIRouter

from api import state as app_state
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
    return {
        **model_registry(),
        "live_bots": [
            bot_model_metadata(bot, risk_limits=risk_limits)
            for bot in getattr(state, "bots", []) or []
        ],
    }


@router.get("/config/risk-limits")
async def get_risk_limits():
    """Current deterministic risk limits used before engine submission."""
    state = app_state.get()
    return {"risk_limits": _risk_limits_from_state(state).to_dict()}
