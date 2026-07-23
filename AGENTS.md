# AGENTS.md

This file is the first stop for coding agents working in this repository.

## Project

Market Simulation Platform is an AI trading arena. Claude/OpenAI bot personalities trade against a simulated market through a Python scheduler and a C++ limit order book. The system logs decisions, fills, portfolios, retrieved evidence, and live events for a FastAPI API and React dashboard.

Current phase: Phases A-J plus the public-read-only P0-P2 hardening pass are complete for the local/demo product scope. The platform now has evaluation/replay foundations, bot behavior analytics, evidence drilldown, replay comparison reports, bundled replay suites, retrieval benchmark suites/history, model/config metadata, safe agent activity telemetry, local ops job status and requeue commands, MCP auth/approval/trace hardening, protected write APIs, durable audit events, frontend reporting exports/charts, route-level frontend code splitting, mobile/read-only UX polish, CI caching/artifacts, Alembic migrations, multi-stage Docker images, a Render Blueprint for API/frontend/Postgres deployment, recruiter-demo docs, and clean-checkout release docs. Remaining work is outside the local/demo code scope: entering live deployment secrets, running deployed smoke checks, production identity/monitoring/backups, and larger audited datasets if required.

## Start Here

Read these files in order:

1. `PROJECT_OVERVIEW.md` for project status and roadmap.
2. `.agents/ARCHITECTURE.md` for system structure and data flow.
3. `.agents/RAG_AND_OPS.md` for SEC ingestion, embeddings, and retrieval.
4. `.agents/PHASE_C_AGENT_TOOLS.md` for risk checks and MCP-style tools.
5. `.agents/PHASE_D_EVALUATION.md` for evaluation metrics, replay storage, and no-lookahead RAG.
6. `.agents/REMAINING_WORK.md` for the full backlog across frontend, evals, replay, MCP/OpenAI, Docker, CI, migrations, and ops.
7. `.agents/TESTING_AND_COMMANDS.md` for verification commands.
8. `.agents/HANDOFF.md` for current state, known limitations, and likely next work.

## Main Directories

- `engine/`: C++17 limit order book, pybind11 bindings, tests, benchmark.
- `simulator/`: bots, scheduler, portfolio, price/news feeds, RAG, risk controls, agent tools, evaluation, replay.
- `simulator/rag/`: SEC ingestion, storage models, repository, embeddings, retrieval, monitor.
- `api/`: FastAPI server, routers, app state, WebSocket manager.
- `frontend/`: React/Vite/Tailwind dashboard.
- `scripts/`: operational workers and local tooling.

## Development Rules

- Prefer `pytest -q` for full Python verification.
- Do not require live API keys or network calls in tests.
- Keep deterministic checks in Python where possible; LLM and market-data calls should be mockable.
- The scheduler is the hard gate before orders reach the engine.
- Preserve existing bot fallback behavior: LLM failures return `HOLD`.
- The direct prompt path is the default. Experimental agent tools must stay opt-in unless the project owner asks otherwise.

## Key Commands

```powershell
pytest -q
python scripts/ingest_poller.py --once --tickers AAPL MSFT --db sqlite:///rag.db
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64
python scripts/agent_mcp_server.py --db sqlite:///rag.db
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
python scripts/run_retrieval_suite.py --db sqlite:///rag.db --allow-misses
python scripts/run_replay_matrix.py --provider-sets claude openai --no-orders --report data/replay_runs/matrix_report.json
python scripts/rag_jobs.py --db sqlite:///rag.db summary
python scripts/container_smoke.py
pytest -q simulator/tests/test_evaluation.py simulator/tests/test_replay.py
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```powershell
cd frontend
npm run dev
```

## Environment

Important env vars:

- `DATABASE_URL`: SQLAlchemy database URL for reasoning logs and RAG storage.
- `OPENAI_API_KEY`: OpenAI bot decisions and optional embeddings.
- `OPENAI_PROJECT_ID`: optional OpenAI Platform project for chat and embedding requests.
- `ANTHROPIC_API_KEY`: optional Claude bot decisions; Claude bots fall back to `HOLD` when absent.
- `NEWS_API_KEY`: live news feed.
- `SEC_USER_AGENT`: SEC EDGAR request identity.
- `STARTING_CASH`: optional simulated starting cash per bot; defaults to `100000`.
- `ANALYST_AGENT_TOOLS_ENABLED`: set to `true` to enable AnalystBot's experimental tool-backed path.
- `AGENT_MCP_TOKEN`: optional bearer token for the local MCP-style server.
- `AGENT_MCP_HTTP_TOKEN`: bearer token required to enable the API `/mcp` HTTP bridge.
- `AGENT_MCP_APPROVAL_REQUIRED`: optional comma-separated tools that require approval metadata.
- `AGENT_MCP_ALLOWED_TOOLS` / `AGENT_MCP_BLOCKED_TOOLS`: optional stdio MCP tool allow/block lists.
- `AGENT_MCP_HTTP_APPROVAL_REQUIRED`: optional HTTP-specific approval list; defaults to `risk_check_order`.
- `AGENT_MCP_HTTP_ALLOWED_TOOLS` / `AGENT_MCP_HTTP_BLOCKED_TOOLS`: optional HTTP MCP tool allow/block lists.

## Verification Status

Latest known local verification:

```text
157 passed, 1 skipped
```

The skipped test is the optional Python bridge test when the native C++ pybind11 engine module is not built.
