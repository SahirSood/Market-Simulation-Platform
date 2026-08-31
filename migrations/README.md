# Database Migrations

Alembic is configured for the SQLAlchemy tables used by live decisions,
execution orders/fills, public-safe agent activity, RAG, RAG ops job status,
replay storage, and Phase G audit events.

Local commands:

```powershell
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

The app still calls `create_all()` for local demo resilience. For an existing
production database, run `python scripts/prepare_production_migrations.py`
from an authorized shell before a schema upgrade; the live API starts directly
so database migration work cannot block the health check.

For the full clean-checkout release checklist, see `docs/operations/RELEASE.md`.
