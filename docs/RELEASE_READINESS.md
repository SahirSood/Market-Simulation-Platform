# Release Readiness Report

Date: 2026-07-22

## 1. Platform Summary

AI Trading Arena is a public, view-only market simulation dashboard. Claude and
OpenAI bots run matched trading personalities against the same market/news/RAG
context, submit validated orders through the Python scheduler, and execute
against a C++ limit order book when the native engine is available.

The public product story is model-vs-model behavior: returns, decisions,
public-safe agent telemetry, evidence use, risk rejections, fills, replay
comparison, and retrieval quality. Visitors can inspect results, but write/admin
actions require `ARENA_API_KEY` and are not exposed in the frontend.

## 2. Final Architecture

- Frontend: React/Vite dashboard in `frontend/`.
- API: FastAPI app in `api/server.py`.
- Agents: bot personalities and LLM decision logic in `simulator/`.
- Execution: scheduler risk gate in `simulator/scheduler.py`, adapter in
  `simulator/engine_adapter.py`, native C++ book under `engine/`.
- Persistence: SQLAlchemy decision, execution, RAG, replay, and audit tables.
- RAG: SEC ingestion, embedding, retrieval, and benchmark code under
  `simulator/rag/`.
- Deployment: Dockerfiles, safe local Compose, and Render Blueprint.

## 3. Repository Interactions

- Frontend calls FastAPI REST endpoints and WebSocket live events.
- API constructs bots, feeds, RAG repository, audit log, replay store, scheduler,
  and MCP-style local tools at startup.
- Scheduler is the hard gate before any non-HOLD order reaches the engine.
- Reasoning rows store agent decisions; agent-activity rows store public-safe
  model/RAG/MCP/risk/execution telemetry; execution rows store submitted or
  rejected orders and exact fills.
- RAG/replay paths use the same database URL but separate table groups.
- MCP-style tools are local/authenticated and cannot bypass scheduler risk checks
  for live order submission.

## 4. Deployment Instructions

1. Push the current branch and confirm CI passes.
2. Create or update the Render Blueprint from `render.yaml`.
3. Configure host secrets: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
   `NEWS_API_KEY`, `SEC_USER_AGENT`, optional `OPENAI_PROJECT_ID`.
4. Confirm production flags: `PUBLIC_READ_ONLY_MODE=true`,
   `SANDBOX_ENABLED=false`, `ENGINE_NATIVE_REQUIRED=true`,
   `API_HSTS_ENABLED=true`, `API_CORS_ALLOW_LOCALHOST=false`,
   `LLM_MONTHLY_SPEND_LIMIT_USD=20`.
5. Run `alembic upgrade head` before upgrading an existing database.
6. Run:

```powershell
python scripts/check_deploy_env.py --production
python scripts/smoke_deployment.py --api-url https://your-api-domain --frontend-url https://your-frontend-domain
```

## 5. Security Posture

Implemented:

- Public read-only default.
- Protected write endpoints via `ARENA_API_KEY`.
- Public config/ops sanitization.
- Public-safe agent activity timeline without hidden chain-of-thought, raw
  prompts, secrets, or raw tool arguments.
- Sandbox disabled by default and removed from public nav.
- Strict production CORS controls.
- Browser security headers.
- Request body cap.
- In-memory read/write rate limits.
- Tracked-secret scan in CI.
- Safe Compose config that does not load `.env`.
- Deployment env validation without printing secrets.

Remaining before broader public use:

- Provider-side billing caps and alerts must be set outside the app.
- Production monitoring/log retention/backups need to be configured in the host.
- Use a real identity layer before allowing anyone besides the owner to mutate
  state.

## 6. Cost Estimate

Configured app-side cap:

- Daily estimated LLM spend: `$1`.
- Monthly estimated LLM spend: `$20`.
- Provider call budgets split across Claude/OpenAI in `render.yaml`.

Assumptions:

- Ten bots, five per provider.
- 90-minute production bot cycle.
- Prompt caching and unchanged-prompt skips enabled.
- RAG top-K and prompt evidence limits are intentionally small.

The app cap is an internal estimate based on recorded usage and fallback call
estimates. Provider billing dashboards remain the authoritative control.

## 7. Test Coverage And Results

Latest local validation:

```text
pytest -q
179 passed, 1 skipped

npm.cmd run build
passed, route-level code splitting enabled and no Vite chunk-size warning

python scripts/scan_tracked_secrets.py
passed

docker compose config
passed and rendered only non-secret demo values
```

Not verified locally:

- Native C++ build: local machine is missing `cmake`.
- Docker image build: Docker Desktop Linux engine was not running.

CI now covers Python tests, migrations, native engine build/test/smoke, Docker
image builds, frontend build, env validation, Compose config, and tracked-secret
scan.

Hosted verification:

```text
python scripts/smoke_deployment.py --api-url https://market-sim-api.onrender.com --frontend-url https://market-sim-frontend.onrender.com
passed
```

Render `/ready` reported native engine enabled/required, Postgres connected,
scheduler running, RAG configured, and public view-only mode active.

## 8. Known Limitations

- Open resting limit orders are recorded but not rehydrated into the in-memory
  C++ order books after API restart.
- Rate limiting is in-memory per API process.
- Historical replay has no-lookahead RAG protections, but larger audited
  historical datasets are still future work.
- RAG quality depends on available filings, embeddings, and provider keys.
- The public app is view-only; operator actions remain API-key-only.
- Render free web services can sleep after inactivity. During sleep the static
  frontend remains available and the API wakes on request, but the in-process
  scheduler does not continuously advance until the API is awake again.

## 9. Deferred Items

- OAuth/private identity for multi-user operation.
- Production monitoring stack and alert routing.
- Backup/restore automation.
- Open-order rehydration.
- Distributed workers for ingestion/embedding.
- More historical replay datasets and retrieval labels.

## P3 Analysis

P3 is not required for a recruiter-facing public read-only showcase. The current
codebase already demonstrates the important engineering story: LLM agents,
validated structured outputs, RAG evidence, deterministic risk gates, custom
matching engine, replay/evaluation, public-safe observability, cost controls,
Docker/Render packaging, and a polished dashboard.

P3 becomes necessary only if the product goal changes from showcase to operated
multi-user platform. The highest-value P3 items would be:

- Production identity/authorization instead of generated shared-key operator
  auth.
- Hosted monitoring, alerting, log retention, and backup/restore automation.
- Open-order rehydration into the in-memory order books after API restart.
- Larger audited historical replay and retrieval benchmark datasets.
- Distributed ingestion/embedding workers if local database-backed workers fall
  behind.
- External image/dependency vulnerability scanning and release attestations.

For recruiter review, these are acceptable deferred items as long as the demo is
honest about being simulated, read-only, and externally hosted with provider
budgets.

## 10. Operational Checklist

- CI green on the target commit.
- `alembic upgrade head` applied to production DB.
- Native engine present: `/ready` reports `checks.engine.native=true`.
- Provider-side spend caps at or below `$20/month`.
- `PUBLIC_READ_ONLY_MODE=true`, `SANDBOX_ENABLED=false`.
- `ARENA_API_KEY` stored only in host/operator secret storage.
- `scripts/smoke_deployment.py` passes against deployed URLs.
- Render service logs show no startup readiness errors.

## 11. Demo Checklist

- Open Arena and show Claude vs OpenAI performance.
- Show Agent Telemetry to explain model calls, RAG/MCP-style tool calls, risk
  checks, and execution outcomes.
- Open FAQ/glossary to explain DegenBot, RAG, MCP tools, risk gate, and
  no-lookahead protections.
- Open bot drawer and show decision rationale, outcome, evidence count, and PnL.
- Open Book to connect decisions to market structure.
- Open Behavior for agent behavior and risk rejection analytics.
- Open Eval for evidence, replay, and model comparison metrics.
- Open Retrieval for RAG documents and benchmark history.
- Open Setup and confirm only public-safe model/data/budget details appear.

## 12. Rollback Plan

1. Keep the previous known-good Render deployment available.
2. If migration fails, stop deployment and restore from the database backup.
3. If API readiness fails, inspect `/ready` checks and service logs.
4. If frontend deploy fails, roll back the static service to the previous build.
5. If spend spikes, disable scheduler or remove provider keys, then rotate keys
   if exposure is suspected.

## 13. Final Recommendation

Current status: ready for hosted public read-only deployment attempt.

Recommended current status after host validation: ready for limited public
showcase/recruiter review.

Do not call it production-ready until provider-side spend caps are confirmed,
backups and log retention are configured, always-on/background execution is
chosen deliberately, and native engine readiness continues to pass in the
deployed API.
