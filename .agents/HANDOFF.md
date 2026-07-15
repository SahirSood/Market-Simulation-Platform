# Handoff

## Current State

Completed:

- Phase A: stabilize and ops.
- Phase B: ingestion and indexing hardening.
- Phase C: deterministic risk controls and local agent tools.

Verified:

```text
41 passed, 1 skipped
```

## What Works

- Five bot personalities across Claude/OpenAI provider labels.
- Python scheduler with staggered bot cycles and noise traders.
- C++ engine adapter with stub fallback when the native pybind11 module is not built.
- SQLAlchemy reasoning log with JSONL fallback.
- RAG storage for SEC documents and chunks.
- SEC ingestion with retries, raw HTML retention, dedupe, and metrics.
- SEC monitor and poller for new filing detection.
- Batch embedding worker.
- Vector retrieval with FAISS when installed, exact cosine fallback, and keyword fallback.
- Evidence injection into bot prompts.
- Evidence fields persisted and exposed through API models.
- Deterministic scheduler-level risk checks.
- Local in-process agent tool registry.
- MCP-style JSON-RPC adapter and script.
- Experimental AnalystBot tool path behind `ANALYST_AGENT_TOOLS_ENABLED`.

## Most Important Safety Invariants

- The scheduler is the final gate before engine submission.
- Every non-`HOLD` decision must pass `risk_check_order()`.
- Bot-level guardrails are not a replacement for scheduler risk checks.
- Direct prompt behavior remains default.
- Tests should not depend on live services.

## Known Limitations

- The native C++ engine must be built separately for full matching.
- Docker does not yet build the pybind11 engine in-container.
- Live mode depends on API keys and network availability.
- The MCP-style server is lightweight local JSON-RPC/stdio, not a production-authenticated remote deployment.
- Historical replay and no-lookahead evaluation are not implemented yet.
- RAG retrieval has no quality metrics dashboard yet.
- Frontend evidence views can be improved.

## Recommended Next Phase

Phase D: Evaluation and Replay.

Good next tasks:

1. Add retrieval quality checks and evidence citation metrics.
2. Track evidence-backed vs speculative trades in aggregate.
3. Add historical replay with an as-of clock.
4. Prevent lookahead bias in replay RAG retrieval with `as_of_date`.
5. Store run configs.
6. Compare Claude/OpenAI models on identical replay inputs.
7. Improve frontend evidence and risk-rejection views.

## Files Added In Phase C

- `simulator/risk.py`
- `simulator/agent_tools.py`
- `simulator/agent_mcp.py`
- `scripts/agent_mcp_server.py`
- `simulator/tests/test_risk.py`
- `simulator/tests/test_agent_tools.py`
- `AGENTS.md`
- `.agents/ARCHITECTURE.md`
- `.agents/RAG_AND_OPS.md`
- `.agents/PHASE_C_AGENT_TOOLS.md`
- `.agents/TESTING_AND_COMMANDS.md`
- `.agents/HANDOFF.md`

## Files Modified In Phase C

- `simulator/scheduler.py`
- `simulator/bots/analyst_bot.py`
- `simulator/config.py`
- `simulator/main.py`
- `api/server.py`
- `simulator/tests/test_scheduler.py`
- `PROJECT_OVERVIEW.md`
