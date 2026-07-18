# Deployment Runbook

This repo is ready for a container-based deployment. The remaining decisions are
where to host it, where to store secrets, and whether live paid provider access
is enabled.

## Recommended First Host

Use Render or Railway for the first public deployment. Both can build from the
existing Dockerfiles and store secrets outside the repository.

Render has a free/basic `render.yaml` in the repo: the API is a free Docker web
service and the frontend is a free static site. Railway has a backend
`railway.json`; deploy the frontend as a second service from `frontend/Dockerfile`
with `VITE_API_URL` set to the deployed API URL.

## Required Backend Secrets

Set these on the API service:

```text
DATABASE_URL=postgresql://...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
ARENA_API_KEY=...
FRONTEND_URL=https://your-frontend-domain
```

`NEWS_API_KEY` is optional at startup. Without it, the API boots and live news
methods return empty lists until the key is added.

## Required Frontend Build Variable

Set this on the frontend service before building:

```text
VITE_API_URL=https://your-api-domain
```

Vite embeds this value at build time, so changing the API domain requires a
frontend rebuild.

## Deploy Steps

1. Create API and frontend services from the repo Dockerfiles.
2. Add backend secrets to the API service.
3. Add `VITE_API_URL` to the frontend build environment if your host does not
   populate it from the API service URL.
4. Run migrations against production `DATABASE_URL`:

```powershell
alembic upgrade head
```

5. Verify env readiness locally or in the host shell:

```powershell
python scripts/check_deploy_env.py --production
```

6. Smoke-check the deployed app:

```powershell
python scripts/smoke_deployment.py --api-url https://your-api-domain --frontend-url https://your-frontend-domain
```

## Operational Notes

- Do not commit real secrets. Use `.env` only for local development and host
  secret managers for production.
- Docker builds the C++ pybind engine in the API image. Local Windows runs in
  stub mode unless the native extension is built locally.
- `ARENA_API_KEY` protects write endpoints. Rotate it if it is exposed.
- Anthropic currently requires account credits before Claude bots can make live
  API calls.
- Add monitoring, log retention, backups, and production identity before
  treating this as a real public service.
