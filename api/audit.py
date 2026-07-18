"""Helpers for recording compact API audit events."""
from __future__ import annotations

from typing import Any

from api.dependencies import WritePrincipal


def record_audit_event(
    state,
    principal: WritePrincipal | Any | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    status: str = "succeeded",
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
) -> int | None:
    audit_log = getattr(state, "audit_log", None)
    if audit_log is None:
        return None
    actor = getattr(principal, "actor", None) or "unknown"
    auth_method = getattr(principal, "auth_method", None) or "unknown"
    request_id = getattr(principal, "request_id", None)
    return audit_log.record_event(
        action,
        actor=actor,
        auth_method=auth_method,
        target_type=target_type,
        target_id=target_id,
        status=status,
        metadata=metadata or {},
        error=error,
        request_id=request_id,
    )
