"""FastAPI dependency functions shared by all routers."""
from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Header, HTTPException

from api import state as _state_module

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class WritePrincipal:
    actor: str
    auth_method: str = "arena_api_key"
    request_id: str | None = None


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


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in _TRUE_VALUES


def public_read_only_mode_enabled() -> bool:
    """Default to the safest public posture unless explicitly disabled."""
    return bool_env("PUBLIC_READ_ONLY_MODE", True)


def public_ops_detail_enabled() -> bool:
    """Expose low-level ops internals only when an operator opts in."""
    return bool_env("PUBLIC_OPS_DETAIL_ENABLED", not public_read_only_mode_enabled())


def sandbox_enabled() -> bool:
    """Sandbox starts work and writes a local DB, so it is opt-in."""
    return bool_env("SANDBOX_ENABLED", False)


async def require_write_auth(
    x_api_key: str = Header(...),
    x_actor: str | None = Header(None),
    x_request_id: str | None = Header(None),
) -> WritePrincipal:
    """Require X-API-Key on every endpoint that mutates state or starts work."""
    expected = os.getenv("ARENA_API_KEY")
    if not expected:
        raise HTTPException(500, "ARENA_API_KEY not configured on server")
    if x_api_key != expected:
        raise HTTPException(401, "Invalid API key")
    actor = _header_value(x_actor) or "api-key"
    request_id = _header_value(x_request_id)
    return WritePrincipal(
        actor=actor.strip()[:128] or "api-key",
        request_id=request_id.strip()[:128] if request_id else None,
    )


verify_api_key = require_write_auth


def _header_value(value) -> str | None:
    return value if isinstance(value, str) else None
