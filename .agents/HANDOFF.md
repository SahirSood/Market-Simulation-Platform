# Handoff

## Current State

Completed:

- Phase A: stabilize and ops.
- Phase B: ingestion and indexing hardening.
- Phase C: deterministic risk controls and local agent tools.
- Phase D foundation: evaluation metrics, replay storage, and no-lookahead RAG helpers.
- Phase D behavior/evidence increment: bot behavior analytics and evidence drilldown.
- Phase D comparison increment: same-input replay comparison reports.
- Phase D replay dataset increment: bundled deterministic replay fixtures.
- Phase D retrieval/config increment: retrieval benchmark cases/CLI/API/page, model metadata, config/ops surfaces, CI, Alembic baseline, and Docker native-engine build.
- Phase D hardening increment: MCP auth/approval/trace controls, retrieval history, replay matrix automation, persistent RAG job status, Alembic upgrade test, Docker smoke check, and frontend risk/config/trend panels.
- Phase E: expanded retrieval data, retrieval suite runner, liquidity replay fixture, and replay matrix reports.
- Phase F: RAG job summaries, requeue commands, read-only ops summaries, and local ops docs.

Verified:

```text
80 passed, 1 skipped
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
- Bot behavior analytics API endpoints and frontend `/behavior` page.
- Evidence chunk lookup API endpoint and reusable frontend evidence drawer.
- Replay run config/input-fingerprint storage.
- Replay decisions table for model comparison runs.
- As-of RAG wrapper for no-lookahead historical replay.
- Replay CLI for timestamped JSON event files.
- Bundled replay fixtures for earnings beat, earnings miss, Fed shock, AI infrastructure, liquidity rotation, market selloff, and SEC filing risk scenarios.
- Replay matrix JSON reports for repeatable suite runs.
- Replay risk checks, optional order submission, fill summaries, and portfolio snapshots.
- Replay run detail API endpoints and frontend decision drilldown.
- Replay comparison API endpoint and `/eval` comparison panel for runs with shared input fingerprints.
- Retrieval benchmark cases under `data/retrieval_cases/` and `scripts/eval_retrieval.py`.
- Retrieval suite runner in `scripts/run_retrieval_suite.py`.
- Retrieval summary API endpoint and frontend `/retrieval` page.
- Model/prompt/config metadata persisted with live and replay decisions.
- Config/risk API endpoints and frontend `/config` page.
- Read-only ops endpoints for RAG and ingestion status.
- GitHub Actions CI scaffold.
- Alembic baseline migration scaffold.
- API Dockerfile native C++/pybind11 engine build.
- Optional bearer auth and per-tool approvals for the local MCP-style adapter.
- Authenticated API HTTP MCP-style bridge at `/mcp`, plus `/mcp/status` and `/mcp/traces`.
- Persistent local ingestion/embedding job status in `rag_job_status`.
- Local RAG job summary/list/requeue CLI in `scripts/rag_jobs.py`.
- Replay matrix helper for same-input provider runs.
- Retrieval history recording and frontend trend table.
- Docker smoke script and Alembic upgrade test.

## Most Important Safety Invariants

- The scheduler is the final gate before engine submission.
- Every non-`HOLD` decision must pass `risk_check_order()`.
- Bot-level guardrails are not a replacement for scheduler risk checks.
- Direct prompt behavior remains default.
- Tests should not depend on live services.

## Known Limitations

- The native C++ engine still needs build verification in each deployment environment.
- Docker builds and smoke-checks the pybind11 engine in-container, but multi-stage image polish is still future work.
- Live mode depends on API keys and network availability.
- The MCP-style server has lightweight stdio and authenticated HTTP JSON-RPC bridges with opt-in approvals, not a full Streamable HTTP MCP deployment.
- Bundled replay fixtures and replay suite automation exist, but larger real historical market/news datasets are still future work.
- Replay creation is not exposed as a write API; use `scripts/run_replay.py` or `scripts/run_replay_matrix.py` while the workflow is still evolving.
- RAG retrieval has starter, operating-metric, and risk/liquidity labeled eval datasets; a larger audited production labeled dataset is still future work.
- Live decision risk rejections are inferred from scheduler reasoning text until `bot_decisions` has a structured risk field.

## Recommended Next Phase

Start Phase G: Secure Control Plane.

For the full finish plan, read `.agents/REMAINING_WORK.md`. The remaining phases are:

1. Phase G: secure write workflows and audit trails.
2. Phase H: full MCP protocol productization only if external clients need it.
3. Phase I: frontend reporting polish and exports.
4. Phase J: release packaging, CI polish, and final docs.

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
- `.agents/REMAINING_WORK.md`
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

## Files Added In Phase D Behavior/Evidence Increment

- `frontend/src/pages/BehaviorPage.jsx`
- `frontend/src/components/evaluation/EvidenceDrawer.jsx`

## Files Modified In Phase D Behavior/Evidence Increment

- `simulator/evaluation.py`
- `simulator/rag/repository.py`
- `api/routers/evaluation.py`
- `api/state.py`
- `api/server.py`
- `frontend/src/App.jsx`
- `frontend/src/api/endpoints.js`
- `frontend/src/components/layout/Navbar.jsx`
- `frontend/src/pages/EvalPage.jsx`
- `api/tests/test_evaluation_router.py`
- `simulator/tests/test_evaluation.py`
- `simulator/rag/tests/test_rag_storage.py`
- `AGENTS.md`
- `.agents/ARCHITECTURE.md`
- `.agents/RAG_AND_OPS.md`
- `.agents/PHASE_D_EVALUATION.md`
- `.agents/REMAINING_WORK.md`
- `.agents/TESTING_AND_COMMANDS.md`
- `.agents/HANDOFF.md`
- `PROJECT_OVERVIEW.md`

## Files Added In Phase D Replay Dataset Increment

- `data/replay_events/README.md`
- `data/replay_events/sample_earnings_beat.json`
- `data/replay_events/sample_earnings_miss.json`
- `data/replay_events/sample_fed_rate_shock.json`
- `data/replay_events/sample_market_selloff.json`
- `data/replay_events/sample_sec_filing_risk.json`
- `simulator/tests/test_replay_datasets.py`

## Files Modified In Phase D Replay Dataset Increment

- `AGENTS.md`
- `PROJECT_OVERVIEW.md`
- `.agents/PHASE_D_EVALUATION.md`
- `.agents/REMAINING_WORK.md`
- `.agents/TESTING_AND_COMMANDS.md`
- `.agents/HANDOFF.md`

## Files Modified In Phase D Comparison Increment

- `simulator/evaluation.py`
- `simulator/replay.py`
- `api/routers/evaluation.py`
- `api/tests/test_evaluation_router.py`
- `simulator/tests/test_evaluation.py`
- `simulator/tests/test_replay.py`
- `frontend/src/api/endpoints.js`
- `frontend/src/pages/EvalPage.jsx`
- `AGENTS.md`
- `.agents/ARCHITECTURE.md`
- `.agents/PHASE_D_EVALUATION.md`
- `.agents/REMAINING_WORK.md`
- `.agents/TESTING_AND_COMMANDS.md`
- `.agents/HANDOFF.md`
- `PROJECT_OVERVIEW.md`
