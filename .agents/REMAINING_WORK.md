# Remaining Work

This document is the backlog for making Market Simulation Platform feel as complete as possible. It starts from the current state: Phase A, Phase B, Phase C, and the Phase D foundation are implemented.

## Current Baseline

Working today:

- C++ limit order book with Python adapter and stub fallback.
- Python scheduler, bot personalities, noise traders, portfolio accounting, and reasoning log.
- Claude/OpenAI provider-labeled bot lineup.
- RAG storage, SEC ingestion, monitor/poller, embeddings worker, vector/keyword retrieval, and evidence injection.
- Deterministic scheduler-level risk checks.
- Local agent tool registry and MCP-style JSON-RPC stdio/HTTP adapters with opt-in bearer auth, per-tool approvals, and compact traces.
- Experimental AnalystBot tool path behind `ANALYST_AGENT_TOOLS_ENABLED`.
- Evaluation metrics for citations, speculative trades, unsupported trades, fill rates, and bot behavior.
- Evidence chunk lookup and a reusable frontend evidence drawer for cited RAG chunks.
- Replay storage, input fingerprints, no-lookahead RAG wrapper, replay CLI, replay matrix helper, bundled replay fixtures, replay risk checks, optional order submission, replay drilldown, and same-input replay comparison reports.
- Retrieval benchmark cases, retrieval suite CLI, retrieval history, retrieval API summary, and frontend Retrieval page.
- Model/prompt/config metadata in live and replay decisions, config/risk endpoints, and frontend Config page.
- Read-only ops endpoints for RAG and ingestion status, backed by local `rag_job_status` rows plus CLI requeue commands for ingestion/embedding attempts.
- Alembic migration scaffold plus upgrade smoke test.
- API Docker native-engine build, container smoke check, and GitHub Actions CI scaffold.
- FastAPI API and React dashboard with arena, bots, book, behavior, sandbox, eval, retrieval, and config pages.
- Latest verification: `80 passed, 1 skipped`.

## Remaining Phases

Use these phases to track the path from "working foundation" to "finished, polished, and handoff-ready."

### Phase E: Evaluation Data and Replay Realism

Status: complete for the local/demo product scope.

Purpose: make model/RAG/replay claims credible.

Scope:

- Larger SEC retrieval cases with stable portable labels.
- More realistic replay fixtures and scenario coverage.
- Repeatable replay suites across providers and bot subsets.
- Clear evaluation methodology docs.

Exit criteria:

- Retrieval evals cover enough tickers/forms/topics to catch regressions.
- Replay suite can be run from one command without live APIs.
- Evaluation pages and docs explain what "better" means.

### Phase F: Ops Reliability and Data Lifecycle

Status: complete for the local/demo product scope.

Purpose: make ingestion, embeddings, migrations, and local jobs reliable.

Scope:

- Failed filing retry/requeue commands.
- Embedding retry/requeue commands.
- Read-only health summaries for repeated failures.
- Migration cleanup where the current schema required it.

Exit criteria:

- An operator can see, retry, and explain failed RAG/embedding work.
- Fresh and upgraded databases are covered by tests.
- Ops docs describe normal and failure workflows.

### Phase G: Secure Control Plane

Status: planned.

Purpose: protect any endpoint that starts work or mutates system state.

Scope:

- Shared auth dependency for replay, ingestion, embedding, sandbox, and future write endpoints.
- Audit logs for write actions and tool calls.
- Clear read-only vs write API boundary.
- MCP/order-impacting tools remain approval-gated.

Exit criteria:

- No write path is unauthenticated.
- Write actions are auditable.
- Scheduler risk remains the final hard gate before orders.

### Phase H: MCP and Agent Protocol Productization

Status: optional/planned.

Purpose: make agent-tool access production-shaped if external clients need it.

Scope:

- Full Streamable HTTP MCP compatibility if required.
- Tool filtering by client/agent/mode.
- Durable trace export.
- Small Agents SDK client example or protocol test.

Exit criteria:

- Either the HTTP bridge is explicitly local-only, or external MCP clients can use it with documented auth/approval semantics.

### Phase I: Frontend Polish and Reporting

Status: planned.

Purpose: make the dashboard feel complete and useful beyond a one-off demo.

Scope:

- Empty/error/loading states across eval/replay/RAG/config views.
- Evidence usage, risk rejection, and replay comparison charts.
- Mobile-safe dense tables.
- JSON/CSV exports for reports.

Exit criteria:

- Demo flows work cleanly with empty, partial, and populated data.
- Reports can be shared without querying the database manually.

### Phase J: Release Packaging and Documentation

Status: planned.

Purpose: make the project easy to run, review, and hand off.

Scope:

- Smaller or multi-stage Docker image.
- CI caching/artifacts.
- Final migration, MCP, ops, evaluation, and demo docs.
- Clean-checkout smoke checklist.

Exit criteria:

- A fresh checkout can be validated with documented commands.
- CI failures are easy to diagnose.
- Docs match the actual product surface.

## Highest-Value Next Work

Do these first if the goal is a complete-feeling product:

1. Define the shared write-auth/audit contract for Phase G.
2. Add authenticated write workflows for replay/ingestion/embedding/sandbox actions.
3. Polish eval/replay charts that make the demo easier to understand.
4. Decide whether Phase H full MCP productization is actually needed.

## Bot Behavior Analytics

Purpose: answer "how have the bots actually been acting?" without needing replay.

Status: Phase E local suite complete.

Implemented backend:

- `GET /evaluation/bot-behavior`
- `GET /evaluation/bot-behavior/{bot_id}`
- Aggregates from `ReasoningLog.get_decisions()`:
  - BUY/SELL/HOLD breakdown.
  - Ticker preference counts.
  - Confidence average and trend.
  - Evidence-backed vs speculative vs unsupported decisions.
  - Citation count and unique source count.
  - Fill rate and filled quantity.
  - Risk rejection count inferred from reasoning text until a structured field exists in live decisions.
  - PnL/time series from portfolio snapshots.

Implemented frontend:

- `/behavior` page.
- Per-bot selector rows with action mix and citation rate.
- Bot timeline table with reasoning, evidence ids, risk rejection labels, and fills.
- Charts for confidence, action mix, and portfolio value.

Implemented tests:

- Deterministic behavior-summary tests with fake decisions.
- API router tests.
- Frontend build check.

Remaining polish:

- Add optional grouping by provider, base personality, ticker, and time window.
- Add a structured live risk field to `bot_decisions` instead of inferring rejections from reasoning text.
- Add evidence usage and risk rejection charts over time.

## Evidence Drilldown

Purpose: when a bot cites chunk ids, the UI should show what text/source it relied on.

Status: initial pass complete.

Implemented backend:

- `RagRepository.get_chunks_by_ids()` fetches chunks by ids with document metadata.
- `GET /evaluation/evidence?chunk_ids=1,2,3`.
- Return:
  - chunk id
  - document id
  - ticker
  - form type
  - accession number
  - published date
  - source URL
  - snippet/content
  - start/end positions

Implemented frontend:

- Reusable evidence drawer.
- Drawer links from replay decision rows and behavior timeline rows.
- Show snippet, source URL, ticker/form, filing date, and chunk id.
- Highlight cited vs missing/invalid evidence ids.
- Add unsupported-trade visual state when a trade has no evidence and is not speculative.

Implemented tests:

- Repository test for batch chunk lookup.
- API test for evidence endpoint.
- Frontend build check.

## Replay Datasets

Purpose: make replay usable immediately, not just possible.

Status: initial pass complete.

Implemented files:

- `data/replay_events/README.md`
- `data/replay_events/sample_earnings_beat.json`
- `data/replay_events/sample_earnings_miss.json`
- `data/replay_events/sample_fed_rate_shock.json`
- `data/replay_events/sample_ai_infrastructure_cycle.json`
- `data/replay_events/sample_liquidity_rotation.json`
- `data/replay_events/sample_market_selloff.json`
- `data/replay_events/sample_sec_filing_risk.json`
- `scripts/run_replay_matrix.py --report ...`

Event schema should document:

- `timestamp` or `as_of_time`
- `prices`
- `ohlcv`
- `trending_headlines`
- `recent_headlines`
- `ticker_headlines`
- optional expected notes/outcomes

Design rules:

- No live network needed.
- Small fixtures are fine; realism matters more than volume.
- Use deterministic event order.
- Include at least one event where no-lookahead RAG matters.

Implemented tests:

- `simulator/tests/test_replay_datasets.py` validates fixture JSON shape, timestamp order, price maps, and no-lookahead intent metadata.

Remaining polish:

- Add larger real historical market/news datasets.
- Schedule replay suites or run them in CI with mocked bots.

## Replay And Model Comparison Reports

Purpose: turn replay runs into "who behaved better on the same input?" reports.

Status: initial pass complete.

Implemented backend:

- Compare runs with the same `input_fingerprint`.
- `ReplayStore.list_runs_by_input_fingerprint()`.
- `compare_replay_runs()` helper.
- `GET /evaluation/replay-runs/compare?fingerprint=...`.
- `GET /evaluation/replay-runs/compare?run_id=...`.
- Metrics:
  - decision count
  - trade count
  - BUY/SELL/HOLD mix
  - citation rate
  - speculative rate
  - unsupported trade rate
  - risk rejection rate
  - fill rate
  - filled quantity
  - final replay portfolio value
  - portfolio value change from snapshots
  - max drawdown if enough snapshots exist
- Group by provider, base bot personality, run id, and model config.

Implemented frontend:

- Same-input comparison section in `/eval` after selecting a replay run.
- Run-level comparison table with decisions, trades, citation rate, risk rejection rate, filled quantity, final value, and value change.
- Provider comparison table for each replay run.
- Existing run detail remains linked by selecting runs in the replay list.

Implemented tests:

- Replay comparison helper test.
- Replay store fingerprint lookup test.
- API router comparison test.
- Frontend build check.

Remaining polish:

- Add explicit winner/leader indicators by metric.
- Add per-personality comparison UI rows.
- Add explicit winner/leader indicators for config differences.

Optional exports:

- JSON export.
- CSV export for leaderboard/reporting.

## Retrieval Benchmarking

Purpose: prove RAG quality improves instead of guessing.

Status: Phase E local suite complete.

Implemented files:

- `data/retrieval_cases/README.md`
- `data/retrieval_cases/sec_basic_cases.json`
- `data/retrieval_cases/sec_operating_metrics_cases.json`
- `data/retrieval_cases/sec_risk_liquidity_cases.json`

Implemented script:

- `scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db`
- `scripts/eval_retrieval.py --cases data/retrieval_cases/sec_operating_metrics_cases.json --db sqlite:///rag.db --record`
- `scripts/run_retrieval_suite.py --db sqlite:///rag.db --allow-misses`

Case schema:

- `name`
- `ticker`
- `query_text`
- `as_of_date`
- `expected_chunk_ids`
- `expected_document_ids`
- `expected_accession_nos`
- `expected_source_urls`
- `expected_text_contains`
- `top_k`

Metrics:

- recall@k
- mean reciprocal rank
- hit rank per case
- returned chunk/document ids, accession numbers, and source URLs

Implemented frontend/API:

- `GET /evaluation/retrieval-summary`
- `GET /evaluation/retrieval-history`
- `/retrieval` page.

Remaining scale-up options:

- Larger audited production labeled case set.
- Persist retrieval history in the database if JSONL history becomes too limiting.

## Model, Prompt, And Config Versioning

Purpose: make comparisons reproducible.

Status: initial pass complete.

Implemented decision metadata:

- exact model name
- provider
- base bot personality
- prompt version
- prompt hash
- RAG top-k
- RAG minimum score
- embedding model
- tool mode enabled/disabled
- risk limits snapshot
- scheduler/replay mode

Implemented replay metadata:

- same fields stored in replay run config.
- same fields stored in replay decision rows.

Implemented files/endpoints:

- `simulator/model_config.py`
- `GET /config/models`
- `GET /config/risk-limits`
- `/config` page.

Remaining:

- Add config hash separate from input fingerprint.
- Add deeper replay config detail if prompt/risk settings start changing often.
- Add explicit prompt version registry if prompts start changing independently.

## OpenAI MCP And Agents SDK Integration

Current state:

- The project has a local MCP-style JSON-RPC/stdio adapter in `simulator/agent_mcp.py`.
- `scripts/agent_mcp_server.py` exposes market/evidence/portfolio/risk tools over local stdio.
- `api/routers/mcp.py` exposes the same adapter over authenticated HTTP at `/mcp`.
- The local adapter supports optional bearer auth, per-tool approvals, structured tool content, and compact in-memory traces.
- AnalystBot has an experimental tool-backed path, but it is custom local plumbing, not a full OpenAI Agents SDK integration.

Goal:

- Make the market tool server usable by OpenAI Agents SDK and/or Responses API MCP integrations without changing the scheduler safety model.

Needed decisions:

- Choose local stdio MCP for local development.
- Choose Streamable HTTP MCP for a locally or remotely hosted service.
- Consider Hosted MCP only if the server is publicly reachable and appropriate for OpenAI-hosted tool execution.
- Keep SSE only for legacy compatibility; prefer Streamable HTTP or stdio for new work.

Needed implementation:

- Replace or complement `AgentMcpAdapter` with a protocol-compliant MCP server implementation.
- Upgrade the HTTP bridge to full Streamable HTTP MCP protocol compatibility if a real external client requires it.
- Keep stdio transport for local tools and tests.
- Define tool schemas with strict, complete descriptions:
  - `market_snapshot`
  - `portfolio_snapshot`
  - `retrieve_evidence`
  - `risk_limits`
  - `risk_check_order`
  - later: `get_replay_run`, `get_bot_behavior`, `get_evidence_chunks`
- Add tool filtering so trading/order-impacting tools can be hidden from some agents.
- Add production approval persistence for any tool that can mutate state or submit orders.
- Expand per-call metadata support for run id, bot id, replay/live mode, trace id, and tenant/environment.
- Export traces to a durable backend if the MCP server becomes long-running.
- Cache `list_tools()` where safe.
- Add tests using a fake MCP client.

Safety rules:

- MCP/tool preflight is advisory.
- Scheduler risk check remains the final hard gate.
- Direct prompt path remains default unless explicitly enabled.
- Mutating MCP tools must require approval or be disabled by default.
- Do not expose live order submission remotely until auth, audit, and approval flows exist.

OpenAI-specific future paths:

- Agents SDK local stdio MCP server for developer experiments.
- Agents SDK HTTP MCP experiments through the authenticated `/mcp` bridge; full Streamable HTTP compatibility remains future work.
- Responses API hosted MCP only after auth, public endpoint, and approval policy are designed.
- Optional OpenAI tracing integration for bot decision and tool-call spans.

## Frontend Completion

Current pages:

- Arena
- Bots
- Book
- Behavior
- Sandbox
- Eval
- Retrieval
- Config

Needed pages/sections:

- Retrieval eval page. (initial pass complete)
- Risk rejection view. (initial bars exist; time-series chart remains)
- Model config/run config view. (initial config page and replay config diff rows exist; detail polish remains)
- Empty states for no DB, no replay runs, no evidence, no API keys.
- Loading and error states for every panel.
- Responsive polish for dense tables on mobile.

Charts to add:

- Evidence usage over time.
- Risk rejections over time.
- Replay provider comparison charts.

## API Completion

Needed endpoints:

- `GET /evaluation/retrieval-summary` (implemented)
- `GET /evaluation/risk-rejections` (implemented)
- `GET /evaluation/retrieval-history` (implemented as JSONL history)
- `GET /evaluation/retrieval-runs` (future DB-backed history if needed)
- `POST /evaluation/retrieval-runs` only if protected by API key.
- `GET /config/models` (implemented)
- `GET /config/risk-limits` (implemented)
- `GET /ops/rag/status` (implemented)
- `GET /ops/ingestion/status` (implemented)

Write endpoint rule:

- Anything that starts replay, ingestion, embedding, sandbox, or order-impacting work must require authentication.

## Database And Migrations

Current state:

- Tables are created with SQLAlchemy `create_all`.
- Some compatibility columns are added manually.
- Alembic baseline and `rag_job_status` migrations exist in `migrations/`.
- A migration upgrade test runs against fresh SQLite.

Needed:

- Replace ad hoc compatibility columns with migrations.
- Add upgrade-path tests from older fixture DBs if this becomes production-operated.

## Docker And Native Engine

Current state:

- Python can use native pybind engine if built locally.
- API Dockerfile installs compiler/CMake/git and builds the native engine.
- API Dockerfile runs `scripts/container_smoke.py --require-native`.
- EngineAdapter falls back to stub mode when native module is missing.

Needed:

- Optionally split build/runtime stages.

## CI And Quality Gates

Status: initial pass complete.

Implemented GitHub Actions:

- Python install.
- `pytest -q`.
- Frontend install and `npm run build`.
- C++ build/CTest.
- API Docker image build, which runs the native-engine smoke check.
- No live API keys required.

Needed:

- Optional C++ build/test matrix beyond the current Linux job.
- Optional lint/type check.
- Cache Python and npm dependencies.

Nice to have:

- Upload test artifacts.
- Run focused tests on PRs and full tests on main.
- Build Docker images on main.

## RAG And Ingestion Ops

Current state:

- SEC ingestion is hardened locally.
- Embedding worker uses DB-backed queue/status behavior.
- `rag_job_status` records local ingestion/embedding attempts and final status.
- Ops endpoints expose recent local job rows and grouped status summaries.
- `scripts/rag_jobs.py` lists, summarizes, and requeues failed/skipped local job rows.

Remaining scale-up options:

- Alerting hooks for repeated failures.
- Optional Redis/RQ or Celery replacement for distributed workers.
- Admin commands for re-ingesting a ticker/form/date range.

## Security And Auth

Needed:

- Keep read-only endpoints open only if intended for local/demo.
- Protect write endpoints with `ARENA_API_KEY` or stronger auth.
- Add auth to replay creation if it ever becomes API-triggered.
- Keep MCP HTTP token-gated and move to stronger auth before any remote deployment.
- Add audit logs for tool calls and write actions.
- Never expose live order submission tools without approval and risk checks.

## Testing Backlog

Needed tests:

- Retrieval eval CLI tests.
- Model config/versioning tests.
- Deeper MCP protocol compliance tests.
- Auth tests for write endpoints.
- Frontend component tests if a JS test stack is added.

## Documentation Backlog

Needed docs:

- Replay event schema.
- Retrieval case schema.
- Bot behavior metrics definitions.
- Model comparison methodology.
- Evidence citation methodology.
- MCP/OpenAI integration guide.
- Docker native engine build notes.
- Database migration guide.
- CI guide.
- Demo script that uses `/eval`, bot behavior, replay, and evidence drilldown.

## Suggested Build Order

1. Protected write APIs for replay/ingestion/embedding/sandbox actions once auth policy is settled.
2. Full Streamable HTTP MCP compatibility with production auth and trace export if external clients require it.
3. Frontend charts for evidence usage, risk rejections over time, and replay comparisons.
4. Larger audited retrieval and historical replay datasets.
5. Distributed ingestion/embedding orchestration and alerting.
