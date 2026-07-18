# MCP And Agent Integration

## Status

Phase H is complete for the local/demo product scope.

This project intentionally keeps the HTTP MCP-style bridge local-only. There is
no concrete external client requirement yet, so the bridge is not advertised as a
full remote Streamable HTTP MCP deployment. The production path is defined: keep
stdio for local development, keep the API HTTP bridge authenticated and audited,
and only implement full remote protocol compatibility when a real client needs
it.

## Transports

- Local stdio: `scripts/agent_mcp_server.py`
- Local authenticated HTTP JSON-RPC: `POST /mcp`
- HTTP status and traces: `GET /mcp/status`, `GET /mcp/traces`

The HTTP bridge requires `Authorization: Bearer {AGENT_MCP_HTTP_TOKEN}`. If
`AGENT_MCP_HTTP_TOKEN` is unset, the endpoint returns 503 and is disabled.

## Tool Policy

Default tools:

- `market_snapshot`
- `portfolio_snapshot`
- `retrieve_evidence`
- `risk_limits`
- `risk_check_order`

Filtering:

- `AGENT_MCP_ALLOWED_TOOLS` or `AGENT_MCP_HTTP_ALLOWED_TOOLS` limits the visible
  and callable tools to a comma-separated allowlist.
- `AGENT_MCP_BLOCKED_TOOLS` or `AGENT_MCP_HTTP_BLOCKED_TOOLS` hides and denies a
  comma-separated blocklist.

Approvals:

- `AGENT_MCP_APPROVAL_REQUIRED` and `AGENT_MCP_HTTP_APPROVAL_REQUIRED` are
  comma-separated tool names requiring `_meta.approved=true`.
- HTTP defaults `risk_check_order` to approval-required when no approval env var
  is set.

`risk_check_order` is advisory. The scheduler remains the final hard gate before
any live order reaches the engine.

## Metadata And Traces

Clients can pass safe metadata in top-level `_meta` or `params._meta`:

- `trace_id`
- `client_name`
- `run_id`
- `bot_id`
- `mode`
- `tenant`
- `environment`

In-memory traces keep only method, tool name, status, duration, trace id, and
those safe metadata fields. They do not store tool arguments or outputs.

HTTP tool calls also write durable audit rows in `phase_g_audit_events`. Audit
metadata follows the same no-arguments/no-output rule.

## Local Smoke Client

Run the API with the HTTP bridge enabled:

```powershell
$env:AGENT_MCP_HTTP_TOKEN="dev-token"
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Call the bridge:

```powershell
python scripts/mcp_http_client_example.py --token dev-token tools/list
python scripts/mcp_http_client_example.py --token dev-token call risk_limits
```

For approval-gated tools:

```powershell
python scripts/mcp_http_client_example.py --token dev-token call risk_check_order --approved --arguments-json '{"bot_id":"analyst-001-claude","action":"BUY","ticker":"AAPL","quantity":1}'
```

## External Client Upgrade Path

Before exposing this bridge outside local/demo environments:

1. Replace bearer-token auth with production identity and authorization.
2. Keep tool filtering client-specific.
3. Keep approval persistence for advisory/order-impacting tools.
4. Keep scheduler risk checks as the authoritative gate.
5. Add a protocol-compliance test against the chosen external MCP client.
6. Decide whether durable traces should live in the app database, a log backend,
   or a tracing backend.
