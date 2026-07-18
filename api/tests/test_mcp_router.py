import asyncio
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from api import state as app_state
from api.routers.mcp import get_mcp_status, get_mcp_traces, post_mcp
from audit import AuditLog


class FakeToolServer:
    def list_tools(self):
        return [
            {
                "name": "risk_limits",
                "description": "Return limits.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "risk_check_order",
                "description": "Check risk.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]

    def call_tool(self, name, arguments=None):
        if name == "risk_limits":
            return {"risk_limits": {"max_order_quantity": 250}}
        raise ValueError(name)


def _init_state(audit_log=None):
    app_state.init(SimpleNamespace(
        agent_tool_server=FakeToolServer(),
        mcp_http_adapter=None,
        audit_log=audit_log,
    ))


def test_http_mcp_is_disabled_without_token(monkeypatch):
    _init_state()
    monkeypatch.delenv("AGENT_MCP_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_MCP_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(post_mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))

    assert exc.value.status_code == 503


def test_http_mcp_lists_calls_and_exports_traces(monkeypatch):
    _init_state()
    monkeypatch.setenv("AGENT_MCP_HTTP_TOKEN", "secret")
    monkeypatch.delenv("AGENT_MCP_HTTP_ALLOWED_TOOLS", raising=False)
    monkeypatch.delenv("AGENT_MCP_HTTP_BLOCKED_TOOLS", raising=False)
    monkeypatch.delenv("AGENT_MCP_HTTP_APPROVAL_REQUIRED", raising=False)
    monkeypatch.delenv("AGENT_MCP_APPROVAL_REQUIRED", raising=False)

    listed = asyncio.run(post_mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        authorization="Bearer secret",
        x_trace_id="trace_test",
    ))
    called = asyncio.run(post_mcp(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "risk_limits", "arguments": {}},
        },
        authorization="Bearer secret",
    ))
    status = asyncio.run(get_mcp_status(authorization="Bearer secret"))
    traces = asyncio.run(get_mcp_traces(authorization="Bearer secret"))

    assert listed["result"]["tools"][0]["name"] == "risk_limits"
    assert called["result"]["structuredContent"]["risk_limits"]["max_order_quantity"] == 250
    assert status["tool_count"] == 2
    assert "risk_check_order" in status["approval_required"]
    assert traces["trace_count"] == 2
    assert "arguments" not in traces["traces"][0]


def test_http_mcp_requires_approval_for_configured_tools(monkeypatch):
    _init_state()
    monkeypatch.setenv("AGENT_MCP_HTTP_TOKEN", "secret")
    monkeypatch.setenv("AGENT_MCP_HTTP_APPROVAL_REQUIRED", "risk_limits")

    denied = asyncio.run(post_mcp(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "risk_limits", "arguments": {}},
        },
        authorization="Bearer secret",
    ))
    approved = asyncio.run(post_mcp(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "risk_limits",
                "arguments": {},
                "_meta": {"approved": True},
            },
        },
        authorization="Bearer secret",
    ))

    assert denied["error"]["code"] == -32001
    assert approved["result"]["structuredContent"]["risk_limits"]["max_order_quantity"] == 250


def test_http_mcp_audits_tool_calls(monkeypatch, tmp_path):
    audit_log = AuditLog(f"sqlite:///{tmp_path / 'audit.db'}")
    _init_state(audit_log=audit_log)
    monkeypatch.setenv("AGENT_MCP_HTTP_TOKEN", "secret")
    monkeypatch.delenv("AGENT_MCP_HTTP_APPROVAL_REQUIRED", raising=False)
    monkeypatch.delenv("AGENT_MCP_HTTP_ALLOWED_TOOLS", raising=False)
    monkeypatch.delenv("AGENT_MCP_HTTP_BLOCKED_TOOLS", raising=False)

    asyncio.run(post_mcp(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "risk_limits",
                "arguments": {"ignored": True},
                "_meta": {"client_name": "smoke", "run_id": "run-1"},
            },
        },
        authorization="Bearer secret",
        x_trace_id="trace_audit",
        x_actor="agent-1",
    ))

    events = audit_log.list_events(action="mcp.tools.call")
    assert events[0]["actor"] == "agent-1"
    assert events[0]["target_id"] == "risk_limits"
    assert events[0]["status"] == "succeeded"
    assert events[0]["metadata"]["client_name"] == "smoke"
    assert events[0]["metadata"]["run_id"] == "run-1"
    assert "arguments" not in events[0]["metadata"]


def test_http_mcp_filters_tools(monkeypatch):
    _init_state()
    monkeypatch.setenv("AGENT_MCP_HTTP_TOKEN", "secret")
    monkeypatch.setenv("AGENT_MCP_HTTP_ALLOWED_TOOLS", "risk_limits")

    listed = asyncio.run(post_mcp(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/list"},
        authorization="Bearer secret",
    ))
    blocked = asyncio.run(post_mcp(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "risk_check_order", "arguments": {}},
        },
        authorization="Bearer secret",
    ))

    assert [tool["name"] for tool in listed["result"]["tools"]] == ["risk_limits"]
    assert blocked["error"]["code"] == -32001
