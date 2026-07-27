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
- Phase G: shared write auth, protected replay/ops/sandbox write APIs, durable audit events, and HTTP MCP tool-call audit rows.
- Phase H: local-only MCP bridge documentation, tool filtering, safer HTTP approvals, safe trace metadata, and a local HTTP client example.
- Phase I: frontend reporting polish, evaluation/retrieval charts, and JSON/CSV exports.
- Phase J: multi-stage Docker packaging, CI caching/artifacts, and clean-checkout release docs.
- Render deployment setup: Blueprint-defined API/frontend/Postgres resources, generated write auth, linked service URLs, and free-tier-compatible startup table initialization for fresh demo databases.
- Public-read-only P0-P2 hardening pass: order-book execution-pricing fix, model decision sanitization, public-safe agent activity telemetry, activity/FAQ/glossary dashboard panels, route-level frontend code splitting, mobile polish, and recruiter-demo docs.

Verified:

```text
180 passed, 1 skipped
```

## What Works

- Five bot personalities across Claude/OpenAI provider labels.
- Python scheduler with staggered bot cycles and noise traders.
- C++ engine adapter with stub fallback when the native pybind11 module is not built.
- SQLAlchemy reasoning log with JSONL fallback.
- Public-safe agent activity rows for model, RAG/MCP-style tool, risk, decision,
  and execution stages.
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
- MCP allow/block filtering, HTTP default approval for `risk_check_order`, safe client/run metadata in traces, and local-only MCP docs in `docs/MCP.md`.
- Persistent local ingestion/embedding job status in `rag_job_status`.
- Local RAG job summary/list/requeue CLI in `scripts/rag_jobs.py`.
- Protected API write endpoints for replay creation, ingestion runs, embedding runs, RAG job requeue, and sandbox start/stop.
- Durable audit rows in `phase_g_audit_events` for protected writes and HTTP MCP tool calls.
- Replay matrix helper for same-input provider runs.
- Retrieval history recording and frontend trend table.
- Frontend JSON/CSV exports for evaluation summaries, provider comparisons, replay details, replay comparisons, retrieval cases/history, bot summaries, and selected-bot timelines.
- Frontend charts for evidence usage, replay comparison rates, retrieval history trends, bot action mix, confidence, and portfolio value.
- Multi-stage API/frontend Docker images, Docker smoke script, Alembic upgrade test, CI dependency caches, and uploaded CI artifacts.
- Render Blueprint with Docker API service, static frontend, managed Postgres, generated `ARENA_API_KEY`, `DATABASE_URL` from Postgres, and `VITE_API_URL`/`FRONTEND_URL` from service URLs. Fresh demo databases initialize at API startup; existing production databases should run `alembic upgrade head` manually before upgrade deploys.
- Release and clean-checkout smoke checklist in `docs/RELEASE.md`.
- Recruiter demo guide in `docs/RECRUITER_DEMO.md`.

## Most Important Safety Invariants

- The scheduler is the final gate before engine submission.
- Every non-`HOLD` decision must pass `risk_check_order()`.
- Bot-level guardrails are not a replacement for scheduler risk checks.
- Direct prompt behavior remains default.
- Tests should not depend on live services.

## Known Limitations

- The native C++ engine still needs build verification in each deployment environment.
- Docker builds and smoke-checks the pybind11 engine in-container, but each deployment environment should still run the release checklist.
- Live mode depends on API keys and network availability.
- Render is configured in repo, but operators still need to enter `OPENAI_API_KEY`, optional `OPENAI_PROJECT_ID`, `ANTHROPIC_API_KEY`, `NEWS_API_KEY`, and `SEC_USER_AGENT` during Blueprint creation and run deployed smoke checks. Anthropic and NewsAPI can be omitted for a boot-only deploy, but they should be present before a public demo.
- The MCP-style server has lightweight stdio and authenticated local HTTP JSON-RPC bridges with filtering, approvals, safe traces, and audit rows. It is explicitly local-only, not a full remote Streamable HTTP MCP deployment.
- Bundled replay fixtures and replay suite automation exist, but larger real historical market/news datasets are still future work.
- API-triggered replay creation is protected by `ARENA_API_KEY`, runs in isolated replay state, and defaults to no order execution.
- RAG retrieval has starter, operating-metric, and risk/liquidity labeled eval datasets; a larger audited production labeled dataset is still future work.
- Live risk, HOLD, and execution outcomes now also emit compact
  `agent_activity_events`; older summary logic still supports legacy
  `bot_decisions` rows.

## Recommended Next Phase

No remaining local/demo code phase is open.

For the full finish plan, read `.agents/REMAINING_WORK.md`. Remaining work is outside the local/demo code scope:

1. Create/sync the Render Blueprint and enter the live OpenAI/SEC/Anthropic/NewsAPI secrets.
2. Run deployed smoke checks against the API and frontend URLs.
3. Choose production identity, monitoring, and image publication policy if this moves beyond demo hosting.
4. Expand audited retrieval and historical replay datasets if production benchmarking is required.

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
