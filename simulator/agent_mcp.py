"""Minimal MCP-style JSON-RPC adapter for local agent tools.

The core tool behavior lives in agent_tools.py. This adapter keeps the transport
thin so the simulator can expose the same tools in-process or over stdio.
"""
from __future__ import annotations

import json
from typing import TextIO


class AgentMcpAdapter:
    def __init__(self, tool_server):
        self.tool_server = tool_server

    def handle(self, request: dict) -> dict:
        method = request.get("method")
        request_id = request.get("id")
        try:
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
                result = {"tools": self.tool_server.list_tools()}
            elif method == "tools/call":
                params = request.get("params", {})
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                self.tool_server.call_tool(
                                    params.get("name"),
                                    params.get("arguments", {}),
                                ),
                                default=str,
                            ),
                        }
                    ]
                }
            else:
                return self._error(request_id, -32601, f"Unknown method: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return self._error(request_id, -32000, str(exc))

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
