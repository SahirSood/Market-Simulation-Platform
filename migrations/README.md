# Database Migrations

Alembic is configured for the SQLAlchemy tables used by live decisions, RAG,
and replay storage.

Local commands:

```powershell
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

The app still calls `create_all()` for local demo resilience, but production
deployments should run migrations explicitly before starting the API.
