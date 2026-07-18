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
- Read-only ops endpoints for RAG and ingestion status, backed by local `rag_job_status` rows plus protected write endpoints and CLI requeue commands for ingestion/embedding attempts.
- Protected replay, ingestion, embedding, RAG requeue, and sandbox write APIs backed by shared `ARENA_API_KEY` auth.
- Durable `phase_g_audit_events` rows for protected writes and HTTP MCP tool calls.
- MCP tool filtering, default HTTP approval for risk preflight, safe metadata traces, local-only MCP docs, and a small HTTP client example.
- Frontend reporting polish with evaluation/retrieval/behavior charts and JSON/CSV exports.
- Alembic migration scaffold plus upgrade smoke test.
- API Docker native-engine build, container smoke check, and GitHub Actions CI scaffold.
- FastAPI API and React dashboard with arena, bots, book, behavior, sandbox, eval, retrieval, and config pages.
- Latest verification: `90 passed, 1 skipped`.

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

Status: complete for the local/demo product scope.

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

Implemented:

- `require_write_auth` centralizes `ARENA_API_KEY` validation and returns an actor/request principal.
- `AuditLog` stores compact durable rows in `phase_g_audit_events`.
- `POST /evaluation/replay-runs` creates isolated replay runs and defaults order execution off.
- `POST /ops/ingestion/run`, `POST /ops/embedding/run`, and `POST /ops/rag/requeue` expose the Phase F local ops workflows behind auth.
- `POST /sandbox/start` and `POST /sandbox/stop` use the same auth/audit path.
- `GET /audit/events` exposes audit reads behind the same protected credential.
- `POST /mcp` records durable audit rows for tool calls without storing arguments or outputs.

### Phase H: MCP and Agent Protocol Productization

Status: complete for the local/demo product scope.

Purpose: make agent-tool access production-shaped if external clients need it.

Scope:

- Full Streamable HTTP MCP compatibility if required.
- Tool filtering by client/agent/mode.
- Durable trace export.
- Small Agents SDK client example or protocol test.

Exit criteria:

- Either the HTTP bridge is explicitly local-only, or external MCP clients can use it with documented auth/approval semantics.

Implemented:

- The HTTP bridge is explicitly documented as local-only in `docs/MCP.md`.
- `AgentMcpAdapter` supports allow/block tool filtering for stdio and HTTP transports.
- HTTP defaults `risk_check_order` to approval-required when no approval env var is set.
- Safe metadata propagation supports trace/client/run/bot/mode/tenant/environment fields without arguments or outputs.
- Durable Phase G audit rows include safe HTTP MCP call metadata.
- `scripts/mcp_http_client_example.py` demonstrates local JSON-RPC list/call flows.
- MCP router and adapter tests cover filtering, approvals, traces, and audit metadata.

### Phase I: Frontend Polish and Reporting

Status: complete for the local/demo product scope.

Purpose: make the dashboard feel complete and useful beyond a one-off demo.

Scope:

- Empty/error/loading states across eval/replay/RAG/config views.
- Evidence usage, risk rejection, and replay comparison charts.
- Mobile-safe dense tables.
- JSON/CSV exports for reports.

Exit criteria:

- Demo flows work cleanly with empty, partial, and populated data.
- Reports can be shared without querying the database manually.

Implemented:

- Reusable browser-side JSON/CSV export helpers.
- `/eval` evidence usage and replay comparison charts.
- `/eval` summary/provider/risk rejection/replay detail/replay comparison exports.
- `/retrieval` recorded-run trend chart and summary/case/history exports.
- `/behavior` summary and selected-bot timeline exports.
- Table empty states and horizontal overflow guards for dense reporting views.

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

1. Finish release packaging and clean-checkout documentation.
2. Add optional CI artifacts and dependency caching.
3. Keep larger audited retrieval/historical datasets as future production-scale work.

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

Implemented local-productization work:

- The current HTTP bridge is documented as local-only instead of full remote Streamable HTTP MCP.
- Tool schemas are defined by `MarketAgentToolServer.list_tools()`.
- Tool filtering can hide tools from stdio or HTTP clients.
- Approval requirements can be configured per transport; HTTP defaults risk preflight to approval-required.
- Per-call metadata supports run id, bot id, mode, trace id, tenant, environment, and client name.
- HTTP tool-call audit rows provide the durable trace/export path for local/demo use.
- `list_tools()` results are cached per adapter after filtering.
- Tests cover the fake-client integration path.

Safety rules:

- MCP/tool preflight is advisory.
- Scheduler risk check remains the final hard gate.
- Direct prompt path remains default unless explicitly enabled.
- Mutating MCP tools must require approval or be disabled by default.
- Do not expose live order submission remotely until auth, audit, and approval flows exist.

OpenAI-specific future paths if a concrete external client is needed:

- Agents SDK local stdio MCP server for developer experiments.
- Agents SDK HTTP MCP experiments through a future full Streamable HTTP-compatible bridge.
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
- Risk rejection view. (summary bars and CSV export exist; time-series chart is optional future polish)
- Model config/run config view. (initial config page and replay config diff rows exist; detail polish remains)
- Empty states for no DB, no replay runs, no evidence, no API keys.
- Loading and error states for every panel.
- Responsive polish for dense tables on mobile.

Implemented reporting:

- Evidence usage chart.
- Replay comparison rates chart.
- Retrieval history trend chart.
- Bot behavior action, confidence, and portfolio charts.
- JSON/CSV exports for evaluation, replay comparison, replay detail, retrieval cases/history, and bot behavior timelines.

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
- `POST /evaluation/replay-runs` (implemented, protected)
- `POST /ops/ingestion/run` (implemented, protected)
- `POST /ops/embedding/run` (implemented, protected)
- `POST /ops/rag/requeue` (implemented, protected)
- `GET /audit/events` (implemented, protected)

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

Implemented:

- Read-only demo endpoints remain separated from protected write paths.
- API write endpoints use `ARENA_API_KEY` through `require_write_auth`.
- Replay creation is API-triggerable only through the protected endpoint.
- HTTP MCP remains bearer-token gated and HTTP tool calls are audited.
- Protected writes and HTTP MCP tool calls write compact durable audit rows.
- Live order submission still is not exposed remotely; scheduler risk remains the hard gate.

Remaining production hardening:

- Replace the local shared key with stronger identity/authorization before remote deployment.
- Add role-specific policies if multiple operators or tenants are introduced.

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

1. Release packaging, CI artifacts, and clean-checkout smoke documentation.
2. Larger audited retrieval and historical replay datasets.
3. Distributed ingestion/embedding orchestration and alerting.
4. Optional frontend component tests if a JavaScript test stack is added.
