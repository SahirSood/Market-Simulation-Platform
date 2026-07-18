"""Protected audit-log endpoints for Phase G control-plane activity."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from api import state as app_state
from api.dependencies import WritePrincipal, require_write_auth

router = APIRouter()


@router.get("/audit/events")
async def list_audit_events(
    limit: int = Query(100, ge=1, le=1000),
    action: str | None = None,
    status: str | None = None,
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Return recent protected write/tool audit events."""
    state = app_state.get()
    audit_log = getattr(state, "audit_log", None)
    if audit_log is None:
        raise HTTPException(404, "Audit log is not configured")
    return {
        "events": await asyncio.to_thread(
            audit_log.list_events,
            limit=limit,
            action=action,
            status=status,
        ),
        "principal": {
            "actor": principal.actor,
            "auth_method": principal.auth_method,
        },
    }
