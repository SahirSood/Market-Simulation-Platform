# Release And Smoke Checklist

This project is code-complete for the local/demo product scope when the checks
below pass from a clean checkout. Render is now the configured first deployment
target through `render.yaml`; external deployment still requires live OpenAI
credentials, SEC contact configuration, public read-only deployment settings,
and any production monitoring decisions. See [`DEPLOYMENT.md`](DEPLOYMENT.md)
for Render setup, env placement, and deployed smoke checks.
The final-gate assessment and current release recommendation are in
[`RELEASE_READINESS.md`](RELEASE_READINESS.md).
The public presentation flow for recruiters is in
[`../showcase/RECRUITER_OVERVIEW.md`](../showcase/RECRUITER_OVERVIEW.md).

## Local Prerequisites

- Python 3.11 or 3.12.
- Node.js 20+.
- CMake 3.20+ and a C++17 compiler for native engine builds.
- Docker Desktop or compatible Docker engine for container checks.

## Environment

Copy the sample environment file:

```powershell
Copy-Item .env.example .env
```

Set these values before live runs:

```text
DATABASE_URL=sqlite:///marketsim.db
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
ARENA_API_KEY=local-demo-key
OPENAI_API_KEY=...
OPENAI_PROJECT_ID=...
ANTHROPIC_API_KEY=...
NEWS_API_KEY=...
STARTING_CASH=100000
PUBLIC_READ_ONLY_MODE=true
PUBLIC_OPS_DETAIL_ENABLED=false
SANDBOX_ENABLED=false
ENGINE_NATIVE_REQUIRED=true
API_SECURITY_HEADERS_ENABLED=true
API_HSTS_ENABLED=true
API_CORS_ALLOW_LOCALHOST=false
API_RATE_LIMIT_ENABLED=true
API_RATE_LIMIT_REQUESTS_PER_MINUTE=240
API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE=30
API_MAX_REQUEST_BODY_BYTES=1048576
LLM_DAILY_SPEND_LIMIT_USD=1
LLM_MONTHLY_SPEND_LIMIT_USD=20
```

`NEWS_API_KEY` is optional at startup; without it, live news calls return empty
lists until a key is added. `ANTHROPIC_API_KEY` is optional for deployment while
the Anthropic account is unavailable; Claude bots fall back to `HOLD`.
`OPENAI_PROJECT_ID` is optional unless you need to force OpenAI calls into a
specific platform project. The API keys are not needed for deterministic tests,
replay fixtures, or Docker image build smoke checks. For a public release, both
OpenAI and Anthropic keys should be configured so the model-vs-model comparison
does not degrade into one active provider and one fallback stream.

## Clean-Checkout Smoke

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
```

Build the frontend:

```powershell
cd frontend
npm ci
npm run build
cd ..
```

Check imports and the native-engine fallback path:

```powershell
python scripts/container_smoke.py
python scripts/check_deploy_env.py
python scripts/run_replay.py --help
python scripts/eval_retrieval.py --help
python scripts/mcp_http_client_example.py --help
```

After building the C++ extension locally, verify the real matching path:

```powershell
python scripts/container_smoke.py --require-native
```

Run migrations against a local SQLite database:

```powershell
$env:DATABASE_URL="sqlite:///smoke.db"
alembic upgrade head
```

The migration head includes the durable execution ledger tables
`execution_orders` and `execution_fills`. The API uses those fill rows to
restore bot portfolios after restart; older data without fill rows falls back
to filled decision summaries.

Build production containers:

```powershell
docker compose build
```

Start the stack:

```powershell
docker compose up
```

The default Compose stack uses local SQLite, offline scheduler mode, and
non-secret demo settings. Do not add real provider keys to `docker-compose.yml`;
use host secrets or a private override file for live local container testing.

Open these URLs:

- API health: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/ready`
- API docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:3000`

## Render Smoke

The Render Blueprint creates the API service, static frontend, and Postgres
database. It wires `DATABASE_URL`, `FRONTEND_URL`, and `VITE_API_URL` from Render
resources, generates `ARENA_API_KEY`, sets `STARTING_CASH=100000`, disables
preview environments, and stays free-tier compatible by leaving pre-deploy
commands out of the Blueprint. Fresh demo databases are initialized by the API
startup path; run `alembic upgrade head` manually before upgrading an existing
production database.

During Blueprint creation, enter:

```text
OPENAI_API_KEY=...
OPENAI_PROJECT_ID=...
ANTHROPIC_API_KEY=...
NEWS_API_KEY=...
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
```

`ANTHROPIC_API_KEY` and `NEWS_API_KEY` can be omitted for a boot-only deploy,
but add them before a public demo if you want Claude bots and live news active.

After Render deploys:

```powershell
python scripts/smoke_deployment.py --api-url https://your-api-domain --frontend-url https://your-frontend-domain
```

This checks API `/health`, API security headers, API `/ready`, API `/docs`,
protected write auth, and the dashboard routes `/`, `/bots`, `/book`,
`/behavior`, `/eval`, `/retrieval`, and `/config`. Sandbox controls are
intentionally removed from the public frontend.

## Demo Path

1. Open the dashboard and confirm arena, bots, book, behavior, eval, retrieval,
   and arena setup navigation.
2. On `/`, show the Agent Telemetry panel and FAQ/glossary so viewers understand
   model calls, RAG/MCP-style tools, risk checks, DegenBot, evidence, and
   read-only restrictions.
3. Open `/eval` and confirm metrics, evidence usage chart, replay comparison
   chart, replay detail drilldown, evidence drawer links, and JSON/CSV exports.
4. Open `/retrieval` and confirm Recall@K/MRR metrics, trend chart, cases,
   recorded runs, and JSON/CSV exports.
5. Open `/behavior` and confirm bot selector, action/confidence/portfolio charts,
   evidence drilldown, and bot/timeline exports.
6. Confirm `/config` shows public-safe arena setup, not database URLs, auth
   flags, MCP status, or worker commands.
7. Use protected write endpoints only with `ARENA_API_KEY` from a private
   operator shell, never from the browser.
8. Confirm provider dashboards have budget alerts or hard spend limits at or
   below `$20/month`; the app-side cap is an internal estimate, not a billing
   authority.

## Packaging Notes

- `api/Dockerfile` uses a builder stage for compilers, CMake, dependency install,
  and native engine build, then runs `container_smoke.py --require-native` before
  publishing the runtime image.
- `frontend/Dockerfile` builds static Vite assets with `npm ci` and serves them
  through nginx on port `3000`.
- `docker-compose.yml` passes `VITE_API_URL` as a frontend build argument because
  Vite embeds that value at build time.
- CI caches pip and npm dependencies, runs Python tests, builds/tests the native
  engine, builds both containers, and uploads Python test logs plus the frontend
  build artifact.
- Open resting limit orders are recorded in the execution ledger but are not
  rehydrated into the in-memory C++ order books after an API restart.
