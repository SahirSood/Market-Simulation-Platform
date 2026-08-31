# Release And Smoke Checklist

This project is code-complete for the local/demo product scope when the checks
below pass from a clean checkout. Render is now the configured first deployment
target through `render.yaml`; external deployment still requires live OpenAI
credentials, SEC contact configuration, public read-only deployment settings,
and deployed-site analytics verification.
See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Render setup, env placement,
analytics, and deployed smoke checks.
The publishable architecture overview lives in the repository `README.md`.

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
VITE_SITE_ANALYTICS_ENABLED=true
VITE_PLAUSIBLE_DOMAIN=your-frontend-domain.example
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
preview environments, keeps the API on Render's paid `starter` web-service plan,
and leaves Postgres on the free plan to keep the first paid step at the
`$7/month` API instance. Fresh demo databases are initialized by the API startup
path, and the API container runs the schema-aware migration prep script before
Uvicorn starts so existing production schemas are reconciled safely.

During Blueprint creation, enter:

```text
OPENAI_API_KEY=...
OPENAI_PROJECT_ID=...
ANTHROPIC_API_KEY=...
NEWS_API_KEY=...
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
VITE_SITE_ANALYTICS_ENABLED=true
SITE_ANALYTICS_GEO_LOOKUP_ENABLED=true
SITE_ANALYTICS_GEO_PROVIDER=ipapi
VITE_PLAUSIBLE_DOMAIN=your-frontend-domain.example
```

`ANTHROPIC_API_KEY` and `NEWS_API_KEY` can be omitted for a boot-only deploy,
but add them before a public demo if you want Claude bots and live news active.

After Render deploys:

```powershell
python scripts/smoke_deployment.py --api-url https://your-api-domain --frontend-url https://your-frontend-domain
```

This checks API `/health`, API security headers, API `/ready`, API `/docs`,
protected write auth, and the product routes `/`, `/brief`, `/research`, and
the research workbench tabs. Sandbox controls are intentionally removed from the
public frontend.

Confirm analytics:

1. Open the deployed frontend with a test UTM URL:

```text
https://your-frontend-domain.example/?utm_source=release-smoke&utm_medium=manual&utm_campaign=market-sim
```

2. Query the protected summary endpoint and confirm the visit appears:

```powershell
Invoke-RestMethod "https://your-api-domain.example/analytics/summary?days=1" -Headers @{ "X-API-Key" = $env:ARENA_API_KEY }
```

3. Click an outbound link from the deployed site and confirm the summary's
   `outbound_clicks` and `top_outbound_targets` update.
4. Confirm the summary includes `top_countries` and, when the lookup provider
   can identify it, `top_cities`, `top_timezones`, or `top_networks`.
5. Optional: if `VITE_PLAUSIBLE_DOMAIN` is set, confirm the visit also appears
   in Plausible with the expected source/campaign.

## Demo Path

1. Open `/` and confirm the focused trading arena is the first product surface:
   graph, benchmark comparison, latest decisions, orders/fills, positions/PnL,
   and risk state before the recap.
2. Confirm the recap/brief appears under the graph and explains What Changed,
   Benchmark Check, Agent Debate, Evidence, Risk View, caveats, and What Changes
   The View.
3. Confirm `/brief` still works as a secondary deep link for the recap.
4. Open `/research` and confirm the Evidence, Evaluation, Bots, Order Book,
   Behavior, and Config tabs load.
5. In the Evaluation tab, confirm the Evaluation Automation panel, metrics,
   Outcome Lab horizon tabs, replay research, fixture library, replay comparison,
   evidence drawer links, and JSON/CSV exports.
6. In the Evidence tab, confirm Recall@K/MRR metrics, trend chart, cases,
   recorded runs, and JSON/CSV exports.
7. In the Behavior tab, confirm bot selector, action/confidence/portfolio charts,
   evidence drilldown, and bot/timeline exports.
8. Confirm the Config tab shows public-safe arena setup, not database URLs, auth
   flags, MCP status, or worker commands.
9. Use protected write endpoints only with `ARENA_API_KEY` from a private
   operator shell, never from the browser.
10. Confirm provider dashboards have budget alerts or hard spend limits at or
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
