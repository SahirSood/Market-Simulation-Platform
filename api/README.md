# API Service

The API is a FastAPI service for the public trading arena dashboard. It exposes
read-only benchmark data, public-safe configuration, evaluation results,
retrieval metrics, market state, and WebSocket updates. Protected write and ops
routes require `ARENA_API_KEY`.

## Key Files

- `server.py`: application factory, startup lifecycle, scheduler wiring, and
  public route registration.
- `routers/`: feature routers for market data, bots, evaluation, retrieval,
  ops, audit, MCP-style tooling, and WebSockets.
- `models.py`: SQLAlchemy models for decisions, execution ledger rows, RAG
  records, replay runs, and audit data.
- `middleware.py`: CORS, security headers, body-size limits, and rate limiting.
- `tests/`: API and deployment-contract tests.

## Local Commands

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
pytest api/tests -q
```

The service expects `DATABASE_URL` and uses `.env` for local development. See
the root `README.md` and `docs/operations/DEPLOYMENT.md` for the full
environment contract.
