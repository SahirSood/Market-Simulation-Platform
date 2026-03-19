"""FastAPI dependency functions — shared by all routers."""
import os
from fastapi import Header, HTTPException
from api import state as _state_module

# ── State accessors ───────────────────────────────────────────────────────────

def get_state():
    return _state_module.get()

def get_bots():
    return _state_module.get().bots

def get_engine():
    return _state_module.get().engine_adapter

def get_reasoning_log():
    return _state_module.get().reasoning_log

def get_price_feed():
    return _state_module.get().price_feed

# ── Auth guard ────────────────────────────────────────────────────────────────

async def verify_api_key(x_api_key: str = Header(...)):
    """Require X-API-Key header on write endpoints (sandbox start/stop)."""
    expected = os.getenv("ARENA_API_KEY")
    if not expected:
        raise HTTPException(500, "ARENA_API_KEY not configured on server")
    if x_api_key != expected:
        raise HTTPException(401, "Invalid API key")
