"""Minimal MCP-style JSON-RPC adapter for local agent tools.

The core tool behavior lives in agent_tools.py. This adapter keeps the transport
thin so the simulator can expose the same tools in-process or over stdio.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import TextIO


SAFE_TRACE_META_KEYS = {
    "trace_id",
    "client_name",
    "run_id",
    "bot_id",
    "mode",
    "tenant",
    "environment",
}


class AgentMcpAdapter:
    def __init__(
        self,
        tool_server,
        auth_token: str | None = None,
        approval_required: set[str] | None = None,
        allowed_tools: set[str] | None = None,
        blocked_tools: set[str] | None = None,
        trace_log_limit: int = 100,
    ):
        self.tool_server = tool_server
        self.auth_token = auth_token if auth_token is not None else os.getenv("AGENT_MCP_TOKEN")
        self.approval_required = approval_required or _csv_set(os.getenv("AGENT_MCP_APPROVAL_REQUIRED"))
        self.allowed_tools = allowed_tools or _csv_set(os.getenv("AGENT_MCP_ALLOWED_TOOLS"))
        self.blocked_tools = blocked_tools or _csv_set(os.getenv("AGENT_MCP_BLOCKED_TOOLS"))
        self.trace_log_limit = max(0, int(trace_log_limit))
        self.traces: list[dict] = []
        self._tool_list_cache: list[dict] | None = None

    def handle(self, request: dict) -> dict:
        method = request.get("method")
        request_id = request.get("id")
        started = time.perf_counter()
        meta = _request_meta(request)
        trace = {
            "trace_id": _trace_id(request),
            "method": method,
            "tool": None,
            "status": "ok",
            "metadata": _trace_metadata(meta),
        }
        try:
            if method != "initialize":
                self._check_auth(request)
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "market-simulation-agent-tools",
                        "version": "1.0.0",
                    },
                    "capabilities": {"tools": {}},
                }
            elif method == "tools/list":
                result = {"tools": self.list_visible_tools()}
            elif method == "tools/call":
                params = request.get("params", {})
                name = params.get("name")
                trace["tool"] = name
                self._check_tool_visible(name)
                self._check_approval(name, params.get("_meta") or request.get("_meta") or {})
                payload = self.tool_server.call_tool(
                    name,
                    params.get("arguments", {}),
                )
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                payload,
                                default=str,
                            ),
                        }
                    ],
                    "structuredContent": payload,
                }
            else:
                trace["status"] = "error"
                return self._error(request_id, -32601, f"Unknown method: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except PermissionError as exc:
            trace["status"] = "denied"
            trace["error"] = str(exc)
            return self._error(request_id, -32001, str(exc))
        except Exception as exc:
            trace["status"] = "error"
            trace["error"] = str(exc)
            return self._error(request_id, -32000, str(exc))
        finally:
            trace["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
            self._record_trace(trace)

    def _check_auth(self, request: dict) -> None:
        if not self.auth_token:
            return
        meta = _request_meta(request)
        value = str(meta.get("authorization") or meta.get("Authorization") or "")
        if value.startswith("Bearer "):
            value = value.removeprefix("Bearer ").strip()
        if value != self.auth_token:
            raise PermissionError("MCP request is missing valid bearer authorization")

    def _check_approval(self, tool_name: str | None, meta: dict) -> None:
        if not tool_name or tool_name not in self.approval_required:
            return
        approved_tools = set(meta.get("approved_tools") or [])
        if meta.get("approved") is True or tool_name in approved_tools:
            return
        raise PermissionError(f"MCP tool '{tool_name}' requires approval")

    def list_visible_tools(self) -> list[dict]:
        if self._tool_list_cache is None:
            self._tool_list_cache = [
                tool
                for tool in self.tool_server.list_tools()
                if self._is_tool_visible(tool.get("name"))
            ]
        return list(self._tool_list_cache)

    def _check_tool_visible(self, tool_name: str | None) -> None:
        if not self._is_tool_visible(tool_name):
            raise PermissionError(f"MCP tool '{tool_name}' is not available for this client")

    def _is_tool_visible(self, tool_name: str | None) -> bool:
        if not tool_name:
            return False
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        if tool_name in self.blocked_tools:
            return False
        return True

    def _record_trace(self, trace: dict) -> None:
        if self.trace_log_limit <= 0:
            return
        self.traces.append(trace)
        del self.traces[:-self.trace_log_limit]

    @staticmethod
    def _error(request_id, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def serve_stdio(self, stdin: TextIO, stdout: TextIO) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle(json.loads(line))
            stdout.write(json.dumps(response, default=str) + "\n")
            stdout.flush()


def _csv_set(value: str | None) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def _request_meta(request: dict) -> dict:
    merged = {}
    meta = request.get("_meta")
    if isinstance(meta, dict):
        merged.update(meta)
    params = request.get("params")
    if isinstance(params, dict) and isinstance(params.get("_meta"), dict):
        merged.update(params["_meta"])
    return merged


def _trace_id(request: dict) -> str:
    meta = _request_meta(request)
    value = meta.get("trace_id")
    if isinstance(value, str) and value.startswith("trace_"):
        return value
    return f"trace_{uuid.uuid4().hex}"


def _trace_metadata(meta: dict) -> dict:
    safe = {}
    for key in SAFE_TRACE_META_KEYS:
        value = meta.get(key)
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
    return safe
