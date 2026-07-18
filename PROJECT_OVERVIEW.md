# Market Simulation Platform: Project Overview and Status

Last updated: July 18, 2026

This is the single source of truth for the project. It combines the old project overview and roadmap/status notes into one handoff document.

For the full remaining-work backlog across frontend, replay, retrieval evals, OpenAI MCP/Agents SDK integration, Docker, CI, migrations, and ops, see `.agents/REMAINING_WORK.md`.

## Finish Plan

The core product is built. The remaining work is about making it complete, polished, secure, and repeatable.

### Phase E: Evaluation Data and Replay Realism

Status: complete for the local/demo product scope.

Goal: make evaluation results convincing instead of just demonstrable.

Done when:

- Retrieval cases include a larger manually labeled SEC set with stable expected sources.
- Replay fixtures include richer historical-style scenarios across earnings, macro, liquidity shocks, and AI/sector rotations.
- Replay matrix runs can be executed as a repeatable suite.
- Evaluation docs explain what metrics mean and how to interpret model comparisons.

### Phase F: Ops Reliability and Data Lifecycle

Status: complete for the local/demo product scope.

Goal: make ingestion, embeddings, and migrations boring to run.

Done when:

- Failed filing and embedding jobs can be retried or requeued cleanly.
- Ops endpoints show enough state to debug ingestion and embedding health.
- Alembic replaces ad hoc compatibility columns where practical.
- CI covers migration upgrade paths and relevant smoke checks.

### Phase G: Secure Control Plane

Status: complete for the local/demo product scope.

Goal: add protected write workflows without opening unsafe trading or ops surfaces.

Done when:

- Replay creation, ingestion triggers, embedding triggers, and sandbox controls use a consistent auth dependency.
- Write actions produce audit records.
- MCP/order-impacting tools remain approval-gated and scheduler risk remains the final hard gate.
- Read-only demo endpoints are clearly separated from protected operations.

Completed in this pass:

- Added a shared `require_write_auth` dependency backed by `ARENA_API_KEY`.
- Added durable `phase_g_audit_events` storage plus Alembic migration.
- Added protected write APIs for replay creation, ingestion runs, embedding runs, RAG job requeue, and sandbox start/stop.
- Added protected audit reads through `GET /audit/events`.
- Added durable audit records for protected writes and HTTP MCP tool calls, without storing API keys, MCP arguments, or tool outputs.
- Kept API-triggered replay isolated from the live arena and defaulted it to no order execution.

### Phase H: MCP and Agent Protocol Productization

Goal: make external agent-tool access production-shaped only if it is actually needed.

Done when:

- The current HTTP MCP-style bridge is upgraded to full Streamable HTTP MCP compatibility, or explicitly documented as local-only if no external client needs it.
- Tool filtering, approval policy, metadata propagation, and trace export are defined.
- A small Agents SDK client example or protocol test proves the integration path.

### Phase I: Frontend Polish and Reporting

Goal: make the dashboard feel finished for demos and repeated use.

Done when:

- Evaluation, behavior, retrieval, and replay views have clear empty/error/loading states.
- Risk rejections, evidence usage, and replay comparisons have useful charts.
- Dense tables are mobile-safe enough for demo use.
- Replay/eval reports can be exported as JSON or CSV.

### Phase J: Release Packaging and Documentation

Goal: make the project easy to run, review, and hand off.

Done when:

- Docker images are smaller or split into build/runtime stages.
- CI caches dependencies and publishes enough artifacts/logs to debug failures.
- README, agent docs, migration docs, MCP docs, and demo script match the actual product.
- A final smoke checklist can validate the app from clean checkout to dashboard.

## Purpose

Market Simulation Platform is an AI trading arena: multiple trading bots compete inside the same simulated market, submit orders into a C++ limit order book, and log their decisions, fills, portfolio state, and evidence.

The project is meant to show three things at once:

- Market structure: limit orders, market orders, price-time priority, fills, liquidity, slippage, portfolios, and PnL.
- Systems engineering: C++ matching engine, Python orchestration, FastAPI service, persistence, Docker scaffolding, and a React dashboard.
- AI engineering: Claude/OpenAI bot personalities, structured decisions, reasoning logs, retrieval-augmented evidence, and a path toward agent tools and evals.

## Current Architecture

```text
         NewsAPI + yfinance + SEC EDGAR
                      |
                      v
        Claude/OpenAI bots + noise traders
                      |
                      v
             Python simulator scheduler
                      |
                      v
          C++ limit order book engine
                      |
                      v
 SQLAlchemy reasoning, portfolio, RAG, replay/eval storage
                      |
                      v
          FastAPI REST + WebSocket API
                      |
                      v
              React/Vite dashboard
```

Main directories:

- `engine/`: C++17 central limit order book, pybind11 bindings, CMake build, benchmark, and engine tests.
- `simulator/`: bot personalities, scheduler, news/price feeds, portfolio accounting, noise traders, reasoning log, RAG integration, evaluation helpers, and replay storage.
- `simulator/rag/`: SEC ingestion, document/chunk storage, embeddings, retrieval, and filing monitor.
- `simulator/risk.py`: deterministic pre-trade risk checks shared by the scheduler and agent tools.
- `simulator/agent_tools.py` and `simulator/agent_mcp.py`: local agent tool registry and MCP-style JSON-RPC adapter.
- `api/`: FastAPI app exposing bots, leaderboard, order book, trades, reasoning, sandbox controls, evaluation metrics, replay runs, config, ops status, and WebSocket events.
- `frontend/`: React/Vite/Tailwind dashboard with arena, bots, book, behavior, sandbox, evaluation, retrieval, and config views.
- `scripts/`: operational helper scripts, including the SEC ingestion poller.

## Implemented System

### Matching Engine

The C++ engine supports a central limit order book with buy/sell books, price-time priority, limit and market orders, cancellations, trade logs, top-of-book snapshots, depth snapshots, benchmarks, tests, and Python bindings.

If the pybind11 module is not built, the Python `EngineAdapter` runs in stub mode so API/simulator development can continue. Full native matching requires building `engine/`.

### Simulator and Bots

The simulator runs five bot personalities for each provider:

- `BearBot`: pessimistic and sell-biased.
- `DegenBot`: aggressive momentum trader.
- `AnalystBot`: cautious limit-order trader.
- `ContrarianBot`: fades crowded intraday moves.
- `MacroBot`: focuses on macro headlines and macro ETFs.

Each personality can run with Claude and OpenAI, giving ten live competitors. Bots emit structured decisions and fall back to `HOLD` when an LLM call fails.

Every non-`HOLD` decision now passes through deterministic scheduler-level risk controls before it can reach the matching engine. Rejected orders are converted to logged `HOLD` decisions with the rejection reason preserved in the reasoning text.

### API and Frontend

The FastAPI backend exposes health checks, bot summaries, bot details, leaderboard, reasoning, order book snapshots, trades, sandbox controls, evaluation metrics, bot behavior analytics, evidence chunk drilldown, retrieval eval summaries, risk rejection summaries, replay runs, model/risk config, ops status, protected control-plane writes, durable audit reads, and live WebSocket events.

The React frontend has arena, bots, order book, bot behavior, sandbox, evaluation, retrieval, and config pages, with components for bot cards, drawers, decisions, leaderboard stats, live feed, comparison charts, order book depth, evidence drilldown, and Phase D metrics.

### Persistence and Reasoning

`ReasoningLog` writes decisions through SQLAlchemy and falls back to local JSONL if the database write fails. Records include bot identity, action, ticker, size, limit price, reasoning, headline, confidence, evidence ids/URLs, fill summary, model/prompt metadata, and portfolio snapshot.

`AuditLog` writes protected control-plane actions to `phase_g_audit_events`. Audit records include actor label, auth method, action, target, status, request id, compact metadata, and error text. They intentionally do not store API keys, MCP arguments, or tool outputs.

Recent hardening:

- Decision reads return detached plain dictionaries for API safety.
- Portfolio `total_value` snapshots now stay JSON-safe even if mark-to-market pricing fails or returns an unexpected value.

### RAG Evidence Layer

The RAG layer currently supports:

- SQLAlchemy models for documents and chunks.
- Document deduplication by content hash.
- SEC EDGAR ingestion for selected tickers and forms.
- Chunking and optional OpenAI embeddings.
- Raw SEC HTML retention alongside cleaned text.
- Batch embedding updates through a database-backed worker script.
- Optional FAISS vector ranking when `faiss`/`numpy` are installed, with exact cosine fallback.
- Keyword fallback retrieval when embeddings are unavailable.
- Evidence injection into bot prompts.
- Evidence ids/URLs persisted with decisions.
- SEC submissions monitoring for new filings.
- As-of retrieval filtering for historical replay/no-lookahead checks.

### Agent Tools and Risk Controls

Phase C added a shared local tool layer:

- `RiskLimits` and `risk_check_order()` in `simulator/risk.py`.
- Scheduler enforcement before every non-`HOLD` engine submission.
- `MarketAgentToolServer` exposing market snapshot, portfolio snapshot, RAG evidence retrieval, risk limits, and risk check tools.
- `AgentMcpAdapter`, `scripts/agent_mcp_server.py`, and `api/routers/mcp.py` for lightweight MCP-style JSON-RPC over stdio or authenticated HTTP.
- Optional MCP bearer auth, per-tool approval checks, structured tool results, and compact trace summaries for local/API tool calls.
- HTTP MCP tool calls now also produce durable Phase G audit events while preserving the compact/no-arguments trace policy.
- Experimental AnalystBot tool path behind `ANALYST_AGENT_TOOLS_ENABLED`; the direct prompt path remains the default.

### Evaluation and Replay Foundation

Phase D now has a deterministic foundation:

- `simulator/evaluation.py` summarizes evidence-backed, speculative, unsupported, cited, filled, and per-bot behavior patterns.
- Provider and bot-level comparison metrics can be computed from ordinary `ReasoningLog` rows.
- `evaluate_retrieval_cases()` supports labeled retrieval checks with recall@k and mean reciprocal rank.
- `simulator/replay.py` stores replay run configs, input fingerprints, and per-event decisions.
- `AsOfRagRepository` wraps RAG retrieval during replay so bots cannot cite future filings.
- `scripts/run_replay.py` runs timestamped JSON event files through provider-labeled bots.
- `scripts/run_replay_matrix.py` runs the same event files across provider sets and can write JSON suite reports.
- `scripts/run_retrieval_suite.py` runs all retrieval case files as one regression suite.
- `data/replay_events/` includes bundled deterministic replay fixtures for earnings, macro, liquidity, sector rotation, selloff, and filing-risk scenarios.
- Replay decisions store risk approval, rejection reason, order id, fill count, filled quantity, and average fill price.
- `GET /evaluation/summary` and `GET /evaluation/replay-runs` expose read-only Phase D API surfaces.
- `GET /evaluation/replay-runs/{run_id}` and `/decisions` expose replay drilldown data.
- `GET /evaluation/replay-runs/compare?fingerprint=...` compares replay runs that used the same event inputs.
- `GET /evaluation/bot-behavior` and `GET /evaluation/bot-behavior/{bot_id}` expose live behavior analytics from reasoning-log rows.
- `GET /evaluation/evidence?chunk_ids=...` returns cited RAG chunks with filing metadata.
- The frontend `/eval` page shows citation/speculation/unsupported-trade metrics, risk rejection bars, provider comparison, replay runs, replay config diffs, same-input replay comparison reports, click-through replay decision details, and evidence drawer links.
- The frontend `/behavior` page shows per-bot action mix, confidence, citation, risk rejection, fill, and portfolio traces.

## Phase A: Stabilize and Ops

Status: complete.

Completed in this pass:

- Added and hardened `RagRepository.get_latest_accession_for_cik()`.
- Normalized CIK values to canonical 10-digit strings on insert and lookup.
- Wired `monitor.detect_new_filings_for_ciks()` to use the repository latest-accession lookup for automatic deduplication.
- Normalized monitor result keys and SEC lookup calls.
- Added `SEC_USER_AGENT` support for SEC requests, with a project default.
- Added `scripts/ingest_poller.py` as a cron/Windows Task-friendly wrapper around detection and ingestion.
- Added poller logging, unknown-ticker reporting, single-run mode, loop mode, interval control, and graceful Ctrl+C shutdown.
- Added deterministic tests for monitor/dedupe behavior.
- Reworked brittle script-style tests so `pytest -q` runs without live NewsAPI/yfinance calls.

Verification:

```powershell
pytest -q
```

Current result:

```text
88 passed, 1 skipped
```

The skipped test is the optional Python bridge test when the native C++ pybind11 module is not built.

## Current Operational Commands

Run all Python tests:

```powershell
pytest -q
```

Check SEC filings for CIKs:

```powershell
python simulator/rag/monitor.py --ciks 0000320193 --max 5
```

Run the SEC poller once:

```powershell
python scripts/ingest_poller.py --once --tickers AAPL MSFT --db sqlite:///rag.db
```

Run the SEC poller continuously:

```powershell
python scripts/ingest_poller.py --tickers AAPL MSFT NVDA --interval-seconds 3600 --db sqlite:///rag.db
```

Run the embedding worker once:

```powershell
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64 --max-retries 1
```

Run the embedding worker continuously:

```powershell
python scripts/embed_worker.py --db sqlite:///rag.db --interval-seconds 60 --batch-size 64
```

Run retrieval benchmark cases:

```powershell
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_operating_metrics_cases.json --db sqlite:///rag.db --record
python scripts/run_retrieval_suite.py --db sqlite:///rag.db --allow-misses
```

Inspect and requeue local RAG jobs:

```powershell
python scripts/rag_jobs.py --db sqlite:///rag.db summary
python scripts/rag_jobs.py --db sqlite:///rag.db list --job-type embedding --status failed
python scripts/rag_jobs.py --db sqlite:///rag.db requeue --job-type embedding --limit 20
```

Protected Phase G write APIs:

```powershell
$headers = @{"X-API-Key"=$env:ARENA_API_KEY; "X-Actor"="local-operator"}
Invoke-RestMethod -Method Post -Uri http://localhost:8000/evaluation/replay-runs -Headers $headers -ContentType "application/json" -Body '{"event_file":"sample_earnings_beat.json","providers":["claude"],"bots":["analyst"],"execute_orders":false}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/ingestion/run -Headers $headers -ContentType "application/json" -Body '{"tickers":["AAPL"],"max_filings":1,"forms":["10-Q"]}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/embedding/run -Headers $headers -ContentType "application/json" -Body '{"limit":100,"batch_size":32}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/rag/requeue -Headers $headers -ContentType "application/json" -Body '{"job_type":"embedding","statuses":["failed"],"limit":20}'
Invoke-RestMethod -Method Get -Uri http://localhost:8000/audit/events -Headers $headers
```

Run the local MCP-style agent tool server:

```powershell
python scripts/agent_mcp_server.py --db sqlite:///rag.db
python scripts/agent_mcp_server.py --db sqlite:///rag.db --token dev-token --approval-required risk_check_order
$env:AGENT_MCP_HTTP_TOKEN="dev-token"
```

Run focused Phase D tests:

```powershell
pytest -q simulator/tests/test_evaluation.py simulator/tests/test_replay.py
```

Run a historical replay event file:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db
python scripts/run_replay_matrix.py --provider-sets claude openai --no-orders --report data/replay_runs/matrix_report.json
```

Enable the experimental AnalystBot tool path:

```powershell
$env:ANALYST_AGENT_TOOLS_ENABLED="true"
```

Suggested Windows Task Scheduler action:

```powershell
python C:\Users\Owner\Desktop\Market-Simulation-Platform\scripts\ingest_poller.py --once --tickers AAPL MSFT NVDA --db sqlite:///C:/Users/Owner/Desktop/Market-Simulation-Platform/rag.db
```

Build the native engine:

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
```

Run the API:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Run the frontend:

```powershell
cd frontend
npm run dev
```

Evaluation page:

```text
http://localhost:5173/eval
```

Behavior page:

```text
http://localhost:5173/behavior
```

Retrieval and Config pages:

```text
http://localhost:5173/retrieval
http://localhost:5173/config
```

## Current Limitations

- Docker now builds and smoke-checks the native C++/pybind11 engine in the API image; image-size polish is still future work.
- Live mode still depends on external API keys and network availability.
- SEC ingestion has retries, metrics, persistent local job status, and local requeue commands; production deployments should still add external orchestration and alerting.
- Embeddings can run in batches through a DB-backed worker with persistent local job status and requeue commands; Redis/RQ or Celery can replace this when distributed workers are needed.
- Vector retrieval uses optional FAISS when installed and falls back to exact cosine search otherwise.
- The MCP-style server has local stdio and authenticated HTTP JSON-RPC bridges with optional auth, approvals, and compact traces; full Streamable HTTP MCP protocol compliance remains future work.
- Historical replay suite automation exists for bundled fixtures; larger real market/news datasets remain future work.
- Bundled replay fixtures cover earnings, macro, liquidity, AI/sector rotation, selloff, and filing-risk scenarios; real historical datasets are still future work.
- Retrieval eval suites include starter, operating-metric, and risk/liquidity cases with CLI history recording and frontend trend history; larger audited production labels are still future work.
- Replay creation is now exposed as a protected write API; API-triggered replays run in isolated replay state and default to no order execution.
- Protected write APIs require `ARENA_API_KEY` and produce durable audit rows in `phase_g_audit_events`.
- Live risk rejections are inferred from scheduler reasoning text in behavior analytics until live decisions gain a structured risk field.

## Roadmap

### Phase B: Improve Ingestion and Indexing

Status: complete as a local production-hardening pass.

Completed:

1. Hardened `simulator/rag/sec_ingestion.py` with retries, exponential backoff, HTTP 429/rate-limit handling, configurable SEC `User-Agent`, and raw HTML retention.
2. Added ingestion metrics: processed, inserted, skipped duplicate, failed fetch, retry count, and last successful accession by CIK.
3. Added batch embedding support through `EmbeddingService.embed_texts()` and repository batch updates.
4. Added `scripts/embed_worker.py`, which treats chunks without embeddings as a database-backed work queue.
5. Added optional FAISS ranking for vector retrieval when `faiss` and `numpy` are installed, with exact cosine fallback when they are not.
6. Added deterministic tests for retry behavior, raw HTML retention, batch embedding, and the embedding worker.

Remaining scale-up option:

- Swap the DB-backed embedding worker for Redis/RQ or Celery when multiple distributed workers are needed.

### Phase C: Agent Tools and Risk Controls

Status: complete as a deterministic local agent-tools pass.

Completed:

1. Added deterministic `risk_check_order()` before every non-`HOLD` engine submission.
2. Added default risk limits for order quantity, order notional, position quantity, position notional, cash after buy, and short-sale prevention.
3. Added `MarketAgentToolServer` exposing market snapshot, portfolio, evidence retrieval, risk limits, and risk check tools.
4. Added `AgentMcpAdapter` plus `scripts/agent_mcp_server.py` as a lightweight local MCP-style JSON-RPC/stdio server.
5. Kept the existing direct prompt path as the default behavior.
6. Added an experimental tool-backed AnalystBot path behind `ANALYST_AGENT_TOOLS_ENABLED`.
7. Added deterministic tests for risk controls, scheduler rejection, agent tools, MCP adapter behavior, and AnalystBot tool preflight.

### Phase D: Evaluation and Replay

Status: foundation implemented.

Completed:

1. Added retrieval quality helpers and evidence citation metrics.
2. Added aggregate tracking for speculative, evidence-backed, and unsupported trades.
3. Added no-lookahead RAG support through as-of retrieval and `AsOfRagRepository`.
4. Added replay run and replay decision storage with stable input fingerprints.
5. Added replay CLI support for timestamped JSON event files.
6. Added replay risk checks, optional order submission, and fill summaries.
7. Added read-only evaluation API endpoints and a frontend Evaluation page.
8. Added replay run detail endpoints and frontend replay decision drilldown.
9. Added bot behavior analytics API endpoints and a frontend Behavior page.
10. Added evidence chunk lookup API support and a reusable frontend evidence drawer.
11. Added replay/model comparison reports for runs with identical input fingerprints.
12. Added bundled deterministic replay event fixtures under `data/replay_events/`.
13. Added starter retrieval benchmark cases, retrieval CLI, retrieval API summary, and frontend Retrieval page.
14. Added model/prompt/config metadata snapshots, config/risk API endpoints, and frontend Config page.
15. Added CI, Alembic baseline migrations, ops status endpoints, and API Docker native-engine build.
16. Added MCP auth/approval/trace hardening, retrieval history, replay matrix automation, persistent RAG job status, migration/container smoke tests, and frontend risk/config/trend panels.

### Phase E: Evaluation Data and Replay Realism

Status: complete as a local evaluation-data pass.

Completed:

1. Added a broader SEC risk/liquidity retrieval case file.
2. Added `scripts/run_retrieval_suite.py` for all-case regression runs.
3. Added a liquidity/sector-rotation replay fixture.
4. Added replay matrix JSON report output for repeatable suite runs.
5. Updated retrieval and replay docs around metrics and suite commands.

### Phase F: Ops Reliability and Data Lifecycle

Status: complete as a local ops-reliability pass.

Completed:

1. Added grouped RAG job status summaries.
2. Added repository-level failed/skipped job requeue behavior.
3. Added `scripts/rag_jobs.py` for listing, summarizing, and requeueing local jobs.
4. Exposed job summaries through read-only ops endpoints.
5. Kept requeue write behavior CLI-only during Phase F; Phase G now exposes it through authenticated write APIs.

Next:

1. Phase H: make MCP fully protocol-compatible only if external clients need it.
2. Phase I: polish frontend reporting and exports.
3. Phase J: finish packaging, CI polish, and final docs.

### Phase G: Secure Control Plane

Status: complete as a local secure-control-plane pass.

Completed:

1. Added shared `ARENA_API_KEY` write auth through `require_write_auth`.
2. Added `AuditLog` and `phase_g_audit_events` for protected writes and HTTP MCP tool calls.
3. Added protected replay creation through `POST /evaluation/replay-runs`.
4. Added protected ingestion, embedding, and RAG job requeue endpoints under `/ops`.
5. Updated sandbox start/stop to use the shared dependency and produce audit rows.
6. Kept replay execution isolated from the live scheduler/engine and defaulted API replay orders off.

## Short Handoff

The project now has a working AI trading arena with bot personalities, simulator orchestration, API/frontend surfaces, reasoning persistence, a hardened local RAG evidence pipeline, deterministic pre-trade risk controls, a local MCP-style agent tool layer with stdio/HTTP auth, approvals, and durable audit events, evaluation/replay/behavior/comparison analytics, bundled replay suites, retrieval benchmark suites with history, model/config metadata, protected ops/replay/sandbox write APIs, persistent local ops job status and requeue commands, CI, Alembic migrations, and Docker native-engine smoke checks. The remaining phases are about optional full MCP compatibility, frontend reporting polish, and release packaging.
