# Phase C Agent Tools

## Status

Phase C is complete as a local deterministic pass.

Implemented:

- Deterministic risk checks before every non-`HOLD` engine submission.
- Local agent tool registry for market, portfolio, evidence, and risk tools.
- Lightweight MCP-style JSON-RPC adapter.
- Experimental AnalystBot tool-backed path behind a feature flag.
- Tests for risk checks, scheduler enforcement, tools, adapter, and AnalystBot preflight.

## Risk Controls

Code:

- `simulator/risk.py`
- `simulator/scheduler.py`

Main API:

- `RiskLimits`
- `RiskCheckResult`
- `risk_check_order(bot, decision, price_feed, limits=None)`

Default limits:

- `max_order_quantity`: 250
- `max_order_notional`: 25000.0
- `max_position_quantity`: 500
- `max_position_notional`: 75000.0
- `min_cash_after_buy`: 0.0
- `allow_short_selling`: false

The scheduler calls `risk_check_order()` after the bot returns a non-`HOLD` decision and before `EngineAdapter.submit()`.

If rejected:

- The order is not submitted.
- The decision is converted to `HOLD`.
- The original intended order and rejection reason are appended to `reasoning`.
- The decision is still logged through `ReasoningLog`.

This is the hard safety gate. Bot-level checks are helpful but not authoritative.

## Agent Tool Server

Code:

- `simulator/agent_tools.py`

Class:

- `MarketAgentToolServer`

Tools:

- `market_snapshot`: active tickers, last price, optional order book snapshot.
- `portfolio_snapshot`: bot portfolio by `bot_id`.
- `retrieve_evidence`: RAG evidence rows for ticker/query.
- `risk_limits`: current deterministic limits.
- `risk_check_order`: deterministic risk preflight for a proposed order.

The API and standalone simulator create one shared tool server and pass it to AnalystBot. After bot IDs are provider-labelled, they call `set_bots()` so portfolio and risk tools can resolve live bots.

## MCP-Style Adapter

Code:

- `simulator/agent_mcp.py`
- `scripts/agent_mcp_server.py`

The adapter supports:

- `initialize`
- `tools/list`
- `tools/call`

It uses newline-delimited JSON-RPC over stdio and returns MCP-style `content` payloads.

Run:

```powershell
python scripts/agent_mcp_server.py --db sqlite:///rag.db
```

The standalone script is mostly a local transport/smoke-test path. The live API/simulator path uses `MarketAgentToolServer` in-process with real bots and portfolios.

## AnalystBot Experimental Path

Code:

- `simulator/bots/analyst_bot.py`
- `simulator/config.py`

Default behavior:

- Direct prompt path remains enabled.
- Tool path is disabled unless `ANALYST_AGENT_TOOLS_ENABLED=true` or tests pass `use_agent_tools=True`.

When enabled:

1. AnalystBot builds its normal prompt.
2. It appends `AGENT TOOL CONTEXT`.
3. Tool context includes market snapshot, portfolio snapshot, retrieved evidence, and risk limits.
4. The LLM returns a structured decision.
5. AnalystBot normalizes limit price and quantity.
6. RAG guardrail runs.
7. Agent risk preflight runs.
8. Scheduler still runs the hard risk check before engine submission.

The preflight is advisory from a system-design perspective; the scheduler gate is authoritative.

## Adding New Tools

Add tool behavior to `MarketAgentToolServer.call_tool()` and `list_tools()`.

Keep tool outputs plain dictionaries. This keeps them easy to expose through:

- in-process bot calls
- API endpoints later
- MCP JSON-RPC/stdio
- tests

Add deterministic tests in `simulator/tests/test_agent_tools.py`.
