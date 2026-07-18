# Release And Smoke Checklist

This project is code-complete for the local/demo product scope when the checks
below pass from a clean checkout. External deployment still requires live API
keys, SEC contact configuration, Docker availability, and any production identity
or hosting decisions. See `docs/DEPLOYMENT.md` for provider setup, env placement,
and deployed smoke checks.

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
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
NEWS_API_KEY=...
```

`NEWS_API_KEY` is optional at startup; without it, live news calls return empty
lists until a key is added. The other API keys are not needed for deterministic
tests, replay fixtures, or Docker image build smoke checks.

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

Run migrations against a local SQLite database:

```powershell
$env:DATABASE_URL="sqlite:///smoke.db"
alembic upgrade head
```

Build production containers:

```powershell
docker compose build
```

Start the stack:

```powershell
docker compose up
```

Open these URLs:

- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:3000`

## Demo Path

1. Open the dashboard and confirm arena, bots, book, behavior, sandbox, eval,
   retrieval, and config navigation.
2. Open `/eval` and confirm metrics, evidence usage chart, replay comparison
   chart, replay detail drilldown, evidence drawer links, and JSON/CSV exports.
3. Open `/retrieval` and confirm Recall@K/MRR metrics, trend chart, cases,
   recorded runs, and JSON/CSV exports.
4. Open `/behavior` and confirm bot selector, action/confidence/portfolio charts,
   evidence drilldown, and bot/timeline exports.
5. Use protected write endpoints only with `ARENA_API_KEY`.
6. Keep live LLM/news/SEC polling disabled unless API keys, SEC contact info, and
   network access are intentionally configured.

## Packaging Notes

- `api/Dockerfile` uses a builder stage for compilers, CMake, dependency install,
  and native engine build, then copies only the virtualenv, built engine, API,
  simulator, and smoke script into the runtime image.
- `frontend/Dockerfile` builds static Vite assets with `npm ci` and serves them
  through nginx on port `3000`.
- `docker-compose.yml` passes `VITE_API_URL` as a frontend build argument because
  Vite embeds that value at build time.
- CI caches pip and npm dependencies, runs Python tests, builds/tests the native
  engine, builds both containers, and uploads Python test logs plus the frontend
  build artifact.
