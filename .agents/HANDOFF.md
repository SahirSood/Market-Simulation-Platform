# Handoff

## Current State

Completed:

- Phase A: stabilize and ops.
- Phase B: ingestion and indexing hardening.
- Phase C: deterministic risk controls and local agent tools.
- Phase D foundation: evaluation metrics, replay storage, and no-lookahead RAG helpers.

Verified:

```text
52 passed, 1 skipped
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
- Evidence citation/speculation/unsupported-trade metrics.
- Read-only evaluation API endpoints and frontend `/eval` page.
- Replay run config/input-fingerprint storage.
- Replay decisions table for model comparison runs.
- As-of RAG wrapper for no-lookahead historical replay.
- Replay CLI for timestamped JSON event files.
- Replay risk checks, optional order submission, fill summaries, and portfolio snapshots.
- Replay run detail API endpoints and frontend decision drilldown.

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
- Replay can run JSON event files, but no bundled historical market/news dataset exists yet.
- Replay creation is not exposed as a write API; use `scripts/run_replay.py` while the workflow is still evolving.
- RAG retrieval has helper metrics, but no labeled production eval dataset yet.
- Frontend evidence views can still be improved with decision-level drill-downs.

## Recommended Next Phase

Continue Phase D: Evaluation and Replay.

Good next tasks:

1. Build historical price/news event datasets for the replay CLI.
2. Build labeled retrieval eval fixtures for common SEC questions.
3. Compare Claude/OpenAI models on identical replay inputs by run fingerprint.
4. Add evidence snippet expansion to replay decision rows.
5. Add model config metadata to bot construction for replay runs.
6. Add replay run comparison reports by shared input fingerprint.

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

## Files Added In Phase D Foundation

- `simulator/evaluation.py`
- `simulator/replay.py`
- `api/routers/evaluation.py`
- `frontend/src/pages/EvalPage.jsx`
- `simulator/tests/test_evaluation.py`
- `simulator/tests/test_replay.py`
- `.agents/PHASE_D_EVALUATION.md`
- `scripts/run_replay.py`
- `api/tests/test_evaluation_router.py`

## Files Modified In Phase D Foundation

- `simulator/base_bot.py`
- `simulator/main.py`
- `api/server.py`
- `api/state.py`
- `frontend/src/App.jsx`
- `frontend/src/api/endpoints.js`
- `frontend/src/components/layout/Navbar.jsx`
- `AGENTS.md`
- `.agents/ARCHITECTURE.md`
- `.agents/RAG_AND_OPS.md`
- `.agents/TESTING_AND_COMMANDS.md`
- `.agents/HANDOFF.md`
- `PROJECT_OVERVIEW.md`
