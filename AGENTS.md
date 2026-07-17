# AGENTS.md

This file is the first stop for coding agents working in this repository.

## Project

Market Simulation Platform is an AI trading arena. Claude/OpenAI bot personalities trade against a simulated market through a Python scheduler and a C++ limit order book. The system logs decisions, fills, portfolios, retrieved evidence, and live events for a FastAPI API and React dashboard.

Current phase: Phase A, Phase B, and Phase C are complete. Phase D now has an evaluation/replay foundation plus bot behavior analytics, evidence drilldown, replay comparison reports, bundled replay datasets, retrieval benchmarks/history, model/config metadata, local ops job status, MCP auth/approval/trace hardening, CI, Alembic migrations, and Docker native-engine smoke checks.

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
python scripts/run_replay_matrix.py --events data/replay_events/sample_ai_infrastructure_cycle.json --provider-sets claude openai --no-orders
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
- `ANTHROPIC_API_KEY`: Claude bot decisions.
- `OPENAI_API_KEY`: OpenAI bot decisions and optional embeddings.
- `NEWS_API_KEY`: live news feed.
- `SEC_USER_AGENT`: SEC EDGAR request identity.
- `ANALYST_AGENT_TOOLS_ENABLED`: set to `true` to enable AnalystBot's experimental tool-backed path.
- `AGENT_MCP_TOKEN`: optional bearer token for the local MCP-style server.
- `AGENT_MCP_HTTP_TOKEN`: bearer token required to enable the API `/mcp` HTTP bridge.
- `AGENT_MCP_APPROVAL_REQUIRED`: optional comma-separated tools that require approval metadata.

## Verification Status

Latest known local verification:

```text
75 passed, 1 skipped
```

The skipped test is the optional Python bridge test when the native C++ pybind11 engine module is not built.
