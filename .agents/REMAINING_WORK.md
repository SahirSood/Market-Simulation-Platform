# Remaining Work

This document is the backlog for making Market Simulation Platform feel as complete as possible. It starts from the current state: Phase A, Phase B, Phase C, and the Phase D foundation are implemented.

## Current Baseline

Working today:

- C++ limit order book with Python adapter and stub fallback.
- Python scheduler, bot personalities, noise traders, portfolio accounting, and reasoning log.
- Claude/OpenAI provider-labeled bot lineup.
- RAG storage, SEC ingestion, monitor/poller, embeddings worker, vector/keyword retrieval, and evidence injection.
- Deterministic scheduler-level risk checks.
- Local agent tool registry and MCP-style JSON-RPC/stdio adapter.
- Experimental AnalystBot tool path behind `ANALYST_AGENT_TOOLS_ENABLED`.
- Evaluation metrics for citations, speculative trades, unsupported trades, and fill rates.
- Replay storage, input fingerprints, no-lookahead RAG wrapper, replay CLI, replay risk checks, optional order submission, and replay drilldown.
- FastAPI API and React dashboard with arena, bots, book, sandbox, and eval pages.
- Latest verification: `52 passed, 1 skipped`.

## Highest-Value Next Work

Do these first if the goal is a complete-feeling product:

1. Add bot behavior analytics.
2. Add evidence snippet drilldown.
3. Add replay/model comparison reports.
4. Add bundled replay datasets.
5. Add retrieval benchmark cases and CLI.
6. Add model/prompt/config versioning.
7. Add CI.
8. Add Docker native engine build.
9. Add production database migrations.
10. Harden OpenAI MCP/Agents SDK integration.

## Bot Behavior Analytics

Purpose: answer "how have the bots actually been acting?" without needing replay.

Needed backend:

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
- Optional grouping by provider, base personality, ticker, and time window.

Needed frontend:

- Bot behavior page or `/eval` tab.
- Per-bot cards with action mix, citation rate, speculative rate, unsupported rate, fill rate.
- Bot timeline table with reasoning, evidence ids, risk rejection labels, and fills.
- Charts for confidence over time, action mix over time, evidence usage over time, and PnL over time.

Tests:

- Deterministic behavior-summary tests with fake decisions.
- API router tests.
- Frontend build check.

## Evidence Drilldown

Purpose: when a bot cites chunk ids, the UI should show what text/source it relied on.

Needed backend:

- Repository helper to fetch chunks by ids, including document metadata.
- API endpoint such as `GET /evaluation/evidence?chunk_ids=1,2,3`.
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

Needed frontend:

- Evidence drawer or inline expansion from decision rows.
- Show snippet, source URL, ticker/form, filing date, and chunk id.
- Highlight cited vs missing/invalid evidence ids.
- Add unsupported-trade visual state when a trade has no evidence and is not speculative.

Tests:

- Repository test for batch chunk lookup.
- API test for evidence endpoint.
- Frontend build check.

## Replay Datasets

Purpose: make replay usable immediately, not just possible.

Needed files:

- `data/replay_events/README.md`
- `data/replay_events/sample_earnings_beat.json`
- `data/replay_events/sample_earnings_miss.json`
- `data/replay_events/sample_fed_rate_shock.json`
- `data/replay_events/sample_market_selloff.json`
- `data/replay_events/sample_sec_filing_risk.json`

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

## Replay And Model Comparison Reports

Purpose: turn replay runs into "who behaved better on the same input?" reports.

Needed backend:

- Compare runs with the same `input_fingerprint`.
- Endpoint such as `GET /evaluation/replay-runs/compare?fingerprint=...`.
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
  - realized/unrealized PnL if available from snapshots
  - max drawdown if enough snapshots exist
- Group by provider, base bot personality, run id, and model config.

Needed frontend:

- Replay comparison page or expandable section in `/eval`.
- Side-by-side Claude/OpenAI provider tables.
- Per-personality comparison rows.
- Winner/leader indicators by metric.
- Link back to run details and individual decisions.

Optional exports:

- JSON export.
- CSV export for leaderboard/reporting.

## Retrieval Benchmarking

Purpose: prove RAG quality improves instead of guessing.

Needed files:

- `data/retrieval_cases/README.md`
- `data/retrieval_cases/sec_basic_cases.json`

Needed script:

- `scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db`

Case schema:

- `name`
- `ticker`
- `query_text`
- `as_of_date`
- `expected_chunk_ids`
- `expected_document_ids`
- `top_k`

Metrics:

- recall@k
- mean reciprocal rank
- hit rank per case
- returned chunk/document ids

Needed frontend/API later:

- Retrieval eval summary endpoint.
- Trend over time if eval results are persisted.

## Model, Prompt, And Config Versioning

Purpose: make comparisons reproducible.

Needed decision metadata:

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

Needed replay metadata:

- same fields stored in replay run config.
- config hash separate from input fingerprint.
- model comparison should require same input fingerprint and clearly show differing configs.

Potential files:

- `simulator/model_config.py`
- `simulator/prompt_versions.py`

## OpenAI MCP And Agents SDK Integration

Current state:

- The project has a local MCP-style JSON-RPC/stdio adapter in `simulator/agent_mcp.py`.
- `scripts/agent_mcp_server.py` exposes market/evidence/portfolio/risk tools over local stdio.
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
- Add a Streamable HTTP transport, likely at `/mcp`, if exposing through FastAPI.
- Keep stdio transport for local tools and tests.
- Define tool schemas with strict, complete descriptions:
  - `market_snapshot`
  - `portfolio_snapshot`
  - `retrieve_evidence`
  - `risk_limits`
  - `risk_check_order`
  - later: `get_replay_run`, `get_bot_behavior`, `get_evidence_chunks`
- Add tool filtering so trading/order-impacting tools can be hidden from some agents.
- Add approval policies for any tool that can mutate state or submit orders.
- Add per-call metadata support for run id, bot id, replay/live mode, trace id, and tenant/environment.
- Add tracing for tool calls and failures.
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
- Agents SDK Streamable HTTP MCP server for hosted backend experiments.
- Responses API hosted MCP only after auth, public endpoint, and approval policy are designed.
- Optional OpenAI tracing integration for bot decision and tool-call spans.

## Frontend Completion

Current pages:

- Arena
- Bots
- Book
- Sandbox
- Eval

Needed pages/sections:

- Bot behavior analytics page.
- Evidence drawer/component reusable from bot decisions and replay decisions.
- Replay comparison page.
- Retrieval eval page.
- Risk rejection view.
- Model config/run config view.
- Empty states for no DB, no replay runs, no evidence, no API keys.
- Loading and error states for every panel.
- Responsive polish for dense tables on mobile.

Charts to add:

- PnL over time per bot.
- Action mix over time.
- Confidence over time.
- Evidence usage over time.
- Risk rejections over time.
- Replay provider comparison charts.

## API Completion

Needed endpoints:

- `GET /evaluation/bot-behavior`
- `GET /evaluation/bot-behavior/{bot_id}`
- `GET /evaluation/evidence`
- `GET /evaluation/replay-runs/compare`
- `GET /evaluation/retrieval-runs`
- `POST /evaluation/retrieval-runs` only if protected by API key.
- `GET /config/models`
- `GET /config/risk-limits`
- `GET /ops/rag/status`
- `GET /ops/ingestion/status`

Write endpoint rule:

- Anything that starts replay, ingestion, embedding, sandbox, or order-impacting work must require authentication.

## Database And Migrations

Current state:

- Tables are created with SQLAlchemy `create_all`.
- Some compatibility columns are added manually.
- This is fine locally, but not production-clean.

Needed:

- Add Alembic.
- Create initial migrations for:
  - reasoning log
  - RAG documents/chunks
  - replay runs/decisions
- Replace ad hoc compatibility columns with migrations.
- Add migration command docs.
- Add tests against fresh and upgraded SQLite DBs.

## Docker And Native Engine

Current state:

- Python can use native pybind engine if built locally.
- Docker does not build the native engine.
- EngineAdapter falls back to stub mode when native module is missing.

Needed:

- Update API Dockerfile to install compiler, CMake, and pybind build dependencies.
- Build engine inside image.
- Ensure Python import path points to built module.
- Add container smoke test showing native `OrderBook` is available.
- Optionally split build/runtime stages.

## CI And Quality Gates

Needed GitHub Actions or equivalent:

- Python install.
- `pytest -q`.
- Frontend install and `npm run build`.
- Optional C++ build/test matrix.
- Optional lint/type check.
- No live API keys required.
- Cache Python and npm dependencies.

Nice to have:

- Upload test artifacts.
- Run focused tests on PRs and full tests on main.
- Build Docker images on main.

## RAG And Ingestion Ops

Current state:

- SEC ingestion is hardened locally.
- Embedding worker uses DB-backed queue behavior.

Needed:

- Persistent job status table.
- Failed filing retry queue.
- Embedding job status and retry counters.
- Ops endpoint for ingestion/embedding health.
- Alerting hooks for repeated failures.
- Optional Redis/RQ or Celery replacement for distributed workers.
- Admin commands for re-ingesting a ticker/form/date range.

## Security And Auth

Needed:

- Keep read-only endpoints open only if intended for local/demo.
- Protect write endpoints with `ARENA_API_KEY` or stronger auth.
- Add auth to replay creation if it ever becomes API-triggered.
- Add auth to MCP HTTP transport.
- Add audit logs for tool calls and write actions.
- Never expose live order submission tools without approval and risk checks.

## Testing Backlog

Needed tests:

- Bot behavior summary tests.
- Evidence batch lookup tests.
- Replay comparison tests.
- Retrieval eval CLI tests.
- Model config/versioning tests.
- MCP protocol compliance tests.
- Auth tests for write endpoints.
- Docker/native engine smoke test.
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

1. Bot behavior analytics API and page.
2. Evidence snippet API and UI drawer.
3. Replay comparison API and UI.
4. Sample replay datasets.
5. Retrieval benchmark cases and CLI.
6. Model/prompt/config versioning.
7. OpenAI Agents SDK/MCP compliant local stdio integration.
8. Streamable HTTP MCP transport with auth and approvals.
9. CI.
10. Docker native engine build.
11. Alembic migrations.
12. RAG/embedding ops status and retries.
