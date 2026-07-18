"""Small local HTTP client for the API MCP-style bridge.

Run while the API is up and AGENT_MCP_HTTP_TOKEN is set:

    python scripts/mcp_http_client_example.py --token dev-token tools/list
    python scripts/mcp_http_client_example.py --token dev-token call risk_limits
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call the local HTTP MCP-style bridge")
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    parser.add_argument("--token", default=os.getenv("AGENT_MCP_HTTP_TOKEN"))
    parser.add_argument("--client-name", default="local-smoke-client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("tools/list", help="List visible tools")
    call_parser = subparsers.add_parser("call", help="Call a visible tool")
    call_parser.add_argument("tool_name")
    call_parser.add_argument("--arguments-json", default="{}")
    call_parser.add_argument("--approved", action="store_true")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    if args.command == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "_meta": {"client_name": args.client_name, "mode": "local_smoke"},
        }
    arguments = json.loads(args.arguments_json)
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": args.tool_name,
            "arguments": arguments,
            "_meta": {
                "approved": bool(args.approved),
                "client_name": args.client_name,
                "mode": "local_smoke",
            },
        },
    }


def main() -> int:
    args = parse_args()
    if not args.token:
        raise SystemExit("Set --token or AGENT_MCP_HTTP_TOKEN")

    body = json.dumps(build_payload(args)).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {args.token}",
            "Content-Type": "application/json",
            "X-Actor": args.client_name,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
