# Database Migrations

Alembic is configured for the SQLAlchemy tables used by live decisions,
execution orders/fills, public-safe agent activity, RAG, RAG ops job status,
replay storage, and Phase G audit events.

Local commands:

```powershell
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

The app still calls `create_all()` for local demo resilience, but production
deployments should run migrations explicitly before starting the API.

For the full clean-checkout release checklist, see `docs/RELEASE.md`.
