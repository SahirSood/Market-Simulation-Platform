"""Authenticated HTTP transport for local MCP-style agent tools."""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from agent_mcp import AgentMcpAdapter
from api import state as app_state
from api.audit import record_audit_event

router = APIRouter()


@router.post("/mcp")
async def post_mcp(
    payload: dict[str, Any] | list[dict[str, Any]] = Body(...),
    authorization: str | None = Header(None),
    x_trace_id: str | None = Header(None),
    x_actor: str | None = Header(None),
):
    """Handle one JSON-RPC request or batch over authenticated HTTP."""
    token = _require_http_token(authorization)
    state = app_state.get()
    adapter = _get_or_create_adapter(state, token)
    actor = _optional_header(x_actor) or "mcp-http"
    request_id = _optional_header(x_trace_id)
    principal = SimpleNamespace(
        actor=actor.strip()[:128] or "mcp-http",
        auth_method="mcp_bearer",
        request_id=request_id.strip()[:128] if request_id else None,
    )
    if isinstance(payload, list):
        responses = []
        for row in payload:
            responses.append(await _handle_and_audit(state, adapter, row, authorization, x_trace_id, principal))
        return responses
    if not isinstance(payload, dict):
        raise HTTPException(400, "MCP payload must be a JSON object or batch list")
    return await _handle_and_audit(state, adapter, payload, authorization, x_trace_id, principal)


@router.get("/mcp/status")
async def get_mcp_status(authorization: str | None = Header(None)):
    """HTTP MCP transport status. Requires the same bearer token as tool calls."""
    token = _require_http_token(authorization)
    state = app_state.get()
    adapter = _get_or_create_adapter(state, token)
    tools = await asyncio.to_thread(adapter.list_visible_tools)
    return {
        "enabled": True,
        "transport": "local_http_jsonrpc",
        "local_only": True,
        "tool_count": len(tools),
        "tools": [tool.get("name") for tool in tools],
        "approval_required": sorted(adapter.approval_required),
        "allowed_tools": sorted(adapter.allowed_tools),
        "blocked_tools": sorted(adapter.blocked_tools),
        "trace_count": len(adapter.traces),
        "trace_export": "GET /mcp/traces",
    }


@router.get("/mcp/traces")
async def get_mcp_traces(
    authorization: str | None = Header(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Recent compact MCP trace summaries without tool arguments or outputs."""
    token = _require_http_token(authorization)
    state = app_state.get()
    adapter = _get_or_create_adapter(state, token)
    effective_limit = limit if isinstance(limit, int) else 50
    return {
        "traces": adapter.traces[-effective_limit:][::-1],
        "trace_count": len(adapter.traces),
    }


def _configured_token() -> str | None:
    return (
        os.getenv("AGENT_MCP_HTTP_TOKEN")
        or os.getenv("AGENT_MCP_TOKEN")
        or os.getenv("ARENA_API_KEY")
    )


def _require_http_token(authorization: str | None) -> str:
    token = _configured_token()
    if not token:
        raise HTTPException(503, "HTTP MCP transport disabled; set AGENT_MCP_HTTP_TOKEN or ARENA_API_KEY")
    expected = f"Bearer {token}"
    if not isinstance(authorization, str) or authorization != expected:
        raise HTTPException(401, "Invalid MCP bearer token")
    return token


def _get_or_create_adapter(state, token: str) -> AgentMcpAdapter:
    adapter = getattr(state, "mcp_http_adapter", None)
    if adapter is not None:
        return adapter
    tool_server = getattr(state, "agent_tool_server", None)
    if tool_server is None:
        raise HTTPException(503, "Agent tool server is not configured")
    adapter = AgentMcpAdapter(
        tool_server,
        auth_token=token,
        approval_required=_approval_required(),
        allowed_tools=_allowed_tools(),
        blocked_tools=_blocked_tools(),
        trace_log_limit=_trace_log_limit(),
    )
    state.mcp_http_adapter = adapter
    return adapter


def _approval_required() -> set[str]:
    raw = os.getenv("AGENT_MCP_HTTP_APPROVAL_REQUIRED")
    if raw is None:
        raw = os.getenv("AGENT_MCP_APPROVAL_REQUIRED")
    if raw is None:
        return {"risk_check_order"}
    return {item.strip() for item in raw.split(",") if item.strip()}


def _allowed_tools() -> set[str]:
    raw = os.getenv("AGENT_MCP_HTTP_ALLOWED_TOOLS")
    if raw is None:
        raw = os.getenv("AGENT_MCP_ALLOWED_TOOLS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _blocked_tools() -> set[str]:
    raw = os.getenv("AGENT_MCP_HTTP_BLOCKED_TOOLS")
    if raw is None:
        raw = os.getenv("AGENT_MCP_BLOCKED_TOOLS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _trace_log_limit() -> int:
    try:
        return int(os.getenv("AGENT_MCP_HTTP_TRACE_LIMIT", "200"))
    except ValueError:
        return 200


def _with_http_meta(
    request: dict[str, Any],
    authorization: str | None,
    trace_id: str | None,
) -> dict[str, Any]:
    enriched = dict(request)
    meta = dict(enriched.get("_meta") or {})
    if isinstance(authorization, str) and authorization:
        meta["authorization"] = authorization
    if isinstance(trace_id, str) and trace_id:
        meta["trace_id"] = trace_id
    params = enriched.get("params")
    if isinstance(params, dict) and isinstance(params.get("_meta"), dict):
        for key in ("client_name", "run_id", "bot_id", "mode", "tenant", "environment"):
            if key in params["_meta"] and key not in meta:
                meta[key] = params["_meta"][key]
    enriched["_meta"] = meta
    return enriched


def _optional_header(value) -> str | None:
    return value if isinstance(value, str) else None


async def _handle_and_audit(
    state,
    adapter: AgentMcpAdapter,
    request: dict[str, Any],
    authorization: str | None,
    trace_id: str | None,
    principal,
) -> dict[str, Any]:
    response = await asyncio.to_thread(
        adapter.handle,
        _with_http_meta(request, authorization, trace_id),
    )
    _record_mcp_tool_audit(state, principal, request, response)
    return response


def _record_mcp_tool_audit(
    state,
    principal,
    request: dict[str, Any],
    response: dict[str, Any],
) -> None:
    if not isinstance(request, dict) or request.get("method") != "tools/call":
        return
    params = request.get("params") or {}
    tool_name = params.get("name") if isinstance(params, dict) else None
    request_meta = request.get("_meta") if isinstance(request.get("_meta"), dict) else {}
    params_meta = params.get("_meta") if isinstance(params, dict) and isinstance(params.get("_meta"), dict) else {}
    status = "failed" if isinstance(response, dict) and response.get("error") else "succeeded"
    error = None
    if status == "failed" and isinstance(response.get("error"), dict):
        error = response["error"].get("message")
    record_audit_event(
        state,
        principal,
        "mcp.tools.call",
        target_type="mcp_tool",
        target_id=tool_name,
        status=status,
        metadata={
            "method": "tools/call",
            "approved": bool(params_meta.get("approved") or request_meta.get("approved")),
            "client_name": _safe_meta_value(params_meta.get("client_name") or request_meta.get("client_name")),
            "run_id": _safe_meta_value(params_meta.get("run_id") or request_meta.get("run_id")),
            "bot_id": _safe_meta_value(params_meta.get("bot_id") or request_meta.get("bot_id")),
            "mode": _safe_meta_value(params_meta.get("mode") or request_meta.get("mode")),
            "tenant": _safe_meta_value(params_meta.get("tenant") or request_meta.get("tenant")),
            "environment": _safe_meta_value(params_meta.get("environment") or request_meta.get("environment")),
        },
        error=error,
    )


def _safe_meta_value(value):
    if isinstance(value, (str, int, float, bool)):
        return value
    return None
