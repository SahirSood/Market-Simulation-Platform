# Market Simulation Platform

AI Trading Arena is a capital markets demo project: ten LLM-powered trading bots compete in a simulated market using a custom C++ limit order book. The deployment target is a public, view-only showcase: visitors can inspect live results, model comparisons, evidence, and metrics, while write/admin actions stay private.

The project is built to demonstrate:

- market structure knowledge: limit orders, market orders, price-time priority, fills, liquidity, and PnL;
- systems engineering: C++ engine, Python orchestration, FastAPI, persistence, and a React dashboard;
- AI engineering: model-vs-model agents, personality prompts, structured decisions, public-safe agent telemetry, RAG evidence, local agent tools, risk controls, and evals.

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
 SQLAlchemy reasoning/execution/RAG/replay storage
                     |
                     v
       FastAPI REST + WebSocket API
                     |
                     v
          React/Vite dashboard
```

Main directories:

- `engine/`: C++17 matching engine, CMake build, pybind11 bindings, benchmark, and engine tests.
- `simulator/`: bot personalities, scheduler, news/price feeds, portfolios, noise traders, decision and execution persistence, RAG, evaluation, and replay helpers.
- `api/`: FastAPI app exposing bots, leaderboard, order book, trades, reasoning, evaluation metrics, replay runs, protected ops/replay writes, audit events, an opt-in local sandbox API, and WebSocket events.
- `frontend/`: React/Vite/Tailwind dashboard with route-level code splitting, reporting charts, agent telemetry, FAQ/glossary help, and JSON/CSV exports.
- `PROJECT_OVERVIEW.md`: merged project overview, current status, and roadmap.

## Bot Competition

The live arena creates five trading personalities for each LLM provider:

- BearBot: pessimistic sell-biased trader.
- DegenBot: aggressive momentum trader.
- AnalystBot: cautious limit-order trader.
- ContrarianBot: fades crowded intraday moves.
- MacroBot: trades macro ETFs from macro headlines.

Each personality runs once with Claude and once with OpenAI, giving ten live competitors.

## Requirements

Recommended local tools:

- Python 3.11 or 3.12
- CMake 3.20+
- A C++17 compiler
- Node.js 20+
- PostgreSQL for full live mode, or SQLite for focused tests/sandbox work

Python packages are listed in `requirements.txt`.

Frontend packages are listed in `frontend/package.json`.

## Environment

Copy `.env.example` to `.env` in the project root:

```powershell
Copy-Item .env.example .env
```

Required for full OpenAI live mode:

```text
OPENAI_API_KEY=your_openai_key_here
OPENAI_PROJECT_ID=proj_your_project_id_here
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
DATABASE_URL=postgresql://user:password@localhost:5432/marketsim
ARENA_API_KEY=local-demo-key
STARTING_CASH=100000
PUBLIC_READ_ONLY_MODE=true
SANDBOX_ENABLED=false
ENGINE_NATIVE_REQUIRED=false
API_SECURITY_HEADERS_ENABLED=true
API_HSTS_ENABLED=false
API_CORS_ALLOW_LOCALHOST=true
API_RATE_LIMIT_ENABLED=true
API_MAX_REQUEST_BODY_BYTES=1048576
LLM_MONTHLY_SPEND_LIMIT_USD=20
```

Optional live integrations:

```text
ANTHROPIC_API_KEY=your_anthropic_key_here
NEWS_API_KEY=your_newsapi_key_here
```

Notes:

- `OPENAI_API_KEY` is needed for OpenAI bot decisions and optional embeddings.
- `ANTHROPIC_API_KEY` enables Claude bot decisions; without it, Claude bots fall back to `HOLD`.
- `OPENAI_PROJECT_ID` scopes OpenAI requests to a specific OpenAI Platform project.
- `STARTING_CASH` controls the simulated cash balance each bot starts with.
- `NEWS_API_KEY` is optional at startup; without it, live news calls degrade to empty headline lists.
- `SEC_USER_AGENT` is used for SEC EDGAR requests; set it to a descriptive app/contact string before live polling.
- `DATABASE_URL` is required by the API startup path.
- `PUBLIC_READ_ONLY_MODE=true` hides operator-only config/ops details from public read endpoints.
- `SANDBOX_ENABLED=false` keeps the incomplete self-run sandbox out of the public release.
- `ENGINE_NATIVE_REQUIRED=true` should be set in production so startup and `/ready` fail if the C++ matching engine is unavailable.
- `API_SECURITY_HEADERS_ENABLED`, `API_RATE_LIMIT_ENABLED`, and `API_MAX_REQUEST_BODY_BYTES` control public API hardening. Production should also set `API_HSTS_ENABLED=true` and `API_CORS_ALLOW_LOCALHOST=false`.
- `LLM_MONTHLY_SPEND_LIMIT_USD=20` enforces the internal estimated model budget; also configure provider-side spend limits or alerts.
- `ARENA_API_KEY` protects write endpoints such as replay creation, ingestion/embedding triggers, RAG requeue, and sandbox start/stop.
- The frontend reads `VITE_API_URL`; see `frontend/.env.example`.
- Deployment details are in `docs/DEPLOYMENT.md`; `.env.production.example` lists production secret names without real values.

For local development, you can use SQLite for non-live experiments and tests by passing an explicit SQLite URL where supported. The main API currently expects `DATABASE_URL` to be configured.

## Install

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

## Build the C++ Engine

From the repo root:

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
```

The Python code looks for the compiled pybind11 module under:

```text
engine/build/Debug
```

If the module is not found, the Python `EngineAdapter` can run in stub mode, but the full demo needs the C++ extension built.

Verify the API can see the native engine after building:

```powershell
python scripts/container_smoke.py --require-native
```

## Run the API

From the repo root:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Useful URLs:

- API health: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/ready`
- API docs: `http://localhost:8000/docs`
- Evaluation summary: `http://localhost:8000/evaluation/summary?limit=500`
- Replay run detail: `http://localhost:8000/evaluation/replay-runs/{run_id}`
- WebSocket stream: `ws://localhost:8000/ws/live`

The dashboard `/eval`, `/retrieval`, and `/behavior` pages expose report exports directly in the UI so demo metrics can be shared without manual database queries.
The arena page also exposes public-safe agent telemetry for model calls,
RAG/MCP-style tool calls, risk checks, and execution outcomes without showing
hidden chain-of-thought, raw prompts, secrets, or raw tool arguments.

## Run the Frontend

In another terminal:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

The Docker Compose frontend service uses port `3000`; Vite local dev defaults to `5173`.

## Run with Docker Compose

The repo includes multi-stage Dockerfiles for the API and frontend:

```powershell
docker compose up --build
```

Important:

- Default Docker Compose mode uses a local SQLite database, offline scheduler mode,
  and non-secret demo settings so `docker compose config` does not print API
  keys. Use host-level secrets or a private override file for live provider keys.
- The API image builds Python dependencies and the native C++/pybind11 engine in a builder stage, runs a native-engine smoke check, and starts FastAPI from a smaller runtime stage.
- The frontend image builds static Vite assets with `npm ci` and serves them with nginx on port `3000`.
- `VITE_API_URL` is a frontend build argument in Docker Compose because Vite embeds it during the static build.

## Deploy on Render

`render.yaml` is the configured production Blueprint. It creates:

- `market-sim-api`: Docker web service from `api/Dockerfile`.
- `market-sim-frontend`: static Vite dashboard.
- `market-sim-db`: Render Postgres.

The Blueprint wires `DATABASE_URL`, `FRONTEND_URL`, and `VITE_API_URL` from
Render resources, generates `ARENA_API_KEY`, sets the public view-only flags,
caps estimated LLM spend at `$20/month`, and waits for GitHub checks before
auto-deploying. It stays free-tier compatible by omitting pre-deploy commands;
fresh demo databases are initialized by API startup, while existing production
databases should be migrated manually with `alembic upgrade head`.

During Render Blueprint creation, enter `OPENAI_API_KEY`, `OPENAI_PROJECT_ID` if
your credits are project-scoped, `ANTHROPIC_API_KEY`, `NEWS_API_KEY`, and
`SEC_USER_AGENT`. Anthropic and NewsAPI are optional for process startup, but
the production env checker requires them for the public model-vs-model/live-data
release. See `docs/DEPLOYMENT.md` for the exact runbook and
`docs/RELEASE_READINESS.md` for the current release recommendation.

## Tests

Python tests:

```powershell
pytest -q
```

C++ tests:

```powershell
cmake --build engine/build --config Debug
ctest --test-dir engine/build --output-on-failure -C Debug
```

Frontend build check:

```powershell
cd frontend
npm run build
```

Clean-checkout release smoke checklist:

```powershell
Get-Content docs/RELEASE.md
```

Release-readiness report:

```powershell
Get-Content docs/RELEASE_READINESS.md
```

Recruiter demo guide:

```powershell
Get-Content docs/RECRUITER_DEMO.md
```

RAG embedding worker:

```powershell
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64 --max-retries 1
```

Retrieval benchmark:

```powershell
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_operating_metrics_cases.json --db sqlite:///rag.db --record
```

Focused Phase D evaluation/replay tests:

```powershell
pytest -q api/tests/test_evaluation_router.py simulator/tests/test_evaluation.py simulator/tests/test_replay.py simulator/tests/test_replay_datasets.py simulator/rag/tests/test_rag_storage.py
```

Run replay events from JSON:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db
```

Replay without submitting orders:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db --no-orders
```

Replay provider matrix:

```powershell
python scripts/run_replay_matrix.py --events data/replay_events/sample_ai_infrastructure_cycle.json --provider-sets claude openai --no-orders
```

Protected control-plane writes:

```powershell
$headers = @{"X-API-Key"=$env:ARENA_API_KEY; "X-Actor"="local-operator"}
Invoke-RestMethod -Method Post -Uri http://localhost:8000/evaluation/replay-runs -Headers $headers -ContentType "application/json" -Body '{"event_file":"sample_earnings_beat.json","providers":["claude"],"bots":["analyst"],"execute_orders":false}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/ingestion/run -Headers $headers -ContentType "application/json" -Body '{"tickers":["AAPL"],"max_filings":1,"forms":["10-Q"]}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/embedding/run -Headers $headers -ContentType "application/json" -Body '{"limit":100,"batch_size":32}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/rag/requeue -Headers $headers -ContentType "application/json" -Body '{"job_type":"embedding","statuses":["failed"],"limit":20}'
Invoke-RestMethod -Method Get -Uri http://localhost:8000/audit/events -Headers $headers
```

MCP-style tool server with optional auth and approvals:

```powershell
$env:AGENT_MCP_TOKEN="dev-token"
python scripts/agent_mcp_server.py --db sqlite:///rag.db --approval-required risk_check_order
```

Authenticated HTTP MCP-style bridge:

```powershell
$env:AGENT_MCP_HTTP_TOKEN="dev-token"
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Then call `POST /mcp`, `GET /mcp/status`, or `GET /mcp/traces` with `Authorization: Bearer dev-token`.

Local MCP HTTP client example:

```powershell
python scripts/mcp_http_client_example.py --token dev-token tools/list
python scripts/mcp_http_client_example.py --token dev-token call risk_limits
```

See `docs/MCP.md` for the local-only bridge contract, filtering variables, approval policy, trace metadata, and the external-client upgrade path.

Migrations:

```powershell
alembic upgrade head
python scripts/container_smoke.py
```

The live arena persists agent decisions in `bot_decisions` and execution
attempts/fills in `execution_orders` and `execution_fills`. API restarts restore
bot portfolios from exact fill rows when available, with a compatibility
fallback to older filled-decision summaries.

## Demo Script

Use this flow when presenting the project:

1. Explain the goal: Claude vs OpenAI trading agents compete inside a custom market simulation.
2. Show `engine/` and describe price-time priority, market/limit orders, cancellations, and fills.
3. Show the five bot personality classes in `simulator/bots/`.
4. Start the API and frontend.
5. Open the arena dashboard and leaderboard.
6. Show Agent Telemetry and FAQ/glossary to explain model calls, RAG/MCP-style tools, risk checks, DegenBot, evidence, and public read-only restrictions.
7. Open a bot drawer or reasoning endpoint to show structured decisions and PnL.
8. Show the order book page to connect LLM decisions to market mechanics.
9. Open `/behavior` to show action mix, confidence, citations, risk rejections, fills, and portfolio traces.
10. Open `/eval` to show citation/speculation metrics, evidence usage, replay comparisons, replay decision drilldown, and report exports.
11. Open `/retrieval` to show labeled RAG benchmark results, trend history, and report exports.
12. Open `/config` to show public-safe arena setup, model versions, risk limits, data status, and budget use.
13. Run or describe `scripts/run_replay_matrix.py` as the path for identical-input model comparisons.
14. Explain remaining outside-code work: live API keys, SEC contact identity, production hosting/identity, larger audited eval labels, and distributed ops if scale requires it.

Short interview pitch:

```text
I built an AI trading arena where Claude and OpenAI compete as trading agents.
The agents read market data and news, produce structured trade decisions, and
submit orders into my own C++ limit order book. The platform logs reasoning,
fills, and portfolio state so I can compare model behavior and profitability.
The platform also has deterministic risk controls, local agent tools,
RAG citation metrics, and replay storage for fair evals.
```

## Known Limitations

- RAG ingestion has retries, raw HTML retention, metrics, batch embedding support, and optional FAISS ranking.
- Distributed embedding workers are not wired yet; the current worker uses the database as a simple local queue with persistent local job status.
- The MCP-style server has local stdio and authenticated local HTTP JSON-RPC bridges with filtering, approval checks, compact traces, and audit rows. It is documented as local-only until a concrete external client requires full remote protocol compatibility.
- Risk controls are deterministic and enforced by the scheduler, but limits remain simple: no shorting/leverage, simple market/limit orders, and no advanced liquidity model yet.
- Filled executions are durably logged and replayed into portfolios after API restart. Open resting limit orders are recorded in the ledger but are not rehydrated into the in-memory C++ order books yet.
- Docker uses multi-stage API/frontend images and smoke-checks the C++ pybind11 extension; publishing/scanning images is a deployment concern.
- Live demos depend on external APIs and valid keys.
- Replay storage, no-lookahead RAG helpers, a JSON replay CLI, protected replay creation API, replay drilldown, bundled deterministic replay fixtures, a replay matrix helper, and same-input comparison reports exist. Undated evidence is excluded during historical replay. Larger real historical datasets are still future work.

See `PROJECT_OVERVIEW.md` for the full implementation plan.
