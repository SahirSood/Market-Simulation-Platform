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


class FakeToolServer:
    def list_tools(self):
        return [
            {
                "name": "risk_limits",
                "description": "Return limits.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]

    def call_tool(self, name, arguments=None):
        if name == "risk_limits":
            return {"risk_limits": {"max_order_quantity": 250}}
        raise ValueError(name)


def _init_state():
    app_state.init(SimpleNamespace(
        agent_tool_server=FakeToolServer(),
        mcp_http_adapter=None,
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
    assert status["tool_count"] == 1
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
