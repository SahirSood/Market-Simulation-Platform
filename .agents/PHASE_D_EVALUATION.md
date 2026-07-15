# Phase D Evaluation And Replay

## Status

Phase D has an initial deterministic foundation.

Implemented:

- Evidence citation and speculation metrics for logged bot decisions.
- Provider and bot-level comparison helpers.
- Retrieval quality checks for labeled query/evidence cases.
- Replay run storage for configs, input fingerprints, and per-event bot decisions.
- A replay CLI that runs bots over timestamped JSON events.
- Replay risk checks, optional engine submission, fill summaries, and portfolio snapshots.
- `AsOfRagRepository` to prevent future SEC filings from leaking into historical replay.
- A read-only FastAPI evaluation router.
- A frontend Evaluation page for citation/speculation/unsupported-trade metrics and replay runs.
- Replay run detail endpoints and frontend decision drilldown.

Still future work:

- Model-vs-model replay automation that drives identical events through different model configs.
- Evidence snippet expansion inside replay decision rows.
- Replay run comparison reports by shared input fingerprint.
- Labeled retrieval eval datasets beyond unit-test fixtures.

## Evaluation Metrics

Code:

- `simulator/evaluation.py`
- `api/routers/evaluation.py`
- `frontend/src/pages/EvalPage.jsx`

Main helpers:

- `decision_evidence_status(decision)`
- `summarize_decisions(decisions)`
- `compare_model_groups(decisions, group_by="llm_provider")`
- `evaluate_retrieval_cases(repository, cases, embedding_service=None)`

Decision categories:

- `hold`: no trade.
- `evidence_backed`: trade cites evidence and is not speculative.
- `speculative_evidence_backed`: trade cites evidence and is explicitly speculative.
- `speculative`: trade is speculative and cites no evidence.
- `unsupported`: trade cites no evidence and is not marked speculative.

Important rates:

- `citation_rate`: share of trade decisions that cite at least one evidence chunk.
- `unsupported_trade_rate`: share of trade decisions with no evidence and no speculative flag.
- `speculative_trade_rate`: share of trade decisions marked speculative.
- `fill_rate`: share of trade decisions with filled quantity.

## Replay Storage

Code:

- `simulator/replay.py`

Tables:

- `phase_d_replay_runs`: one row per replay/model-comparison run.
- `phase_d_replay_decisions`: one row per bot decision emitted during a replay event.

Run records include:

- run id
- name
- status
- started/completed timestamps
- config JSON
- input fingerprint
- notes

Decision records include:

- run id
- event index
- as-of time
- bot identity/provider
- action/ticker/quantity/limit price
- reasoning/headline/confidence
- evidence ids/URLs
- speculative flag
- risk approval/rejection reason
- order id
- fill count/quantity/average price
- portfolio snapshot
- event payload

`ReplayStore` is initialized at API and standalone simulator startup so the tables exist whenever `DATABASE_URL` is configured.

## No-Lookahead RAG

Code:

- `simulator/base_bot.py`
- `simulator/replay.py`
- `simulator/rag/repository.py`

`RagRepository.retrieve_evidence()` already accepts `as_of_date` and filters out documents with `published_at` after that date.

Phase D adds:

- `BaseBot._retrieve_evidence()` passes `context["as_of_date"]` when present.
- `AsOfRagRepository` wraps a normal repository and injects the replay event timestamp.

This means historical replay can run against the same RAG store without letting bots cite future SEC filings.

## Replay CLI

Code:

- `scripts/run_replay.py`

Run:

```powershell
python scripts/run_replay.py --events data/replay_events.json --db sqlite:///rag.db
```

Record decisions and risk checks without submitting orders:

```powershell
python scripts/run_replay.py --events data/replay_events.json --db sqlite:///rag.db --no-orders
```

Event file can be either a list:

```json
[
  {
    "timestamp": "2026-01-01T14:30:00Z",
    "prices": {"AAPL": 190.0},
    "recent_headlines": ["AAPL revenue rises"],
    "ticker_headlines": {"AAPL": ["AAPL margin expands"]}
  }
]
```

Or an object with metadata:

```json
{
  "name": "January replay",
  "config": {"source": "fixture"},
  "events": []
}
```

The CLI creates a replay run, builds provider-labeled bots, wraps RAG with `AsOfRagRepository`, applies each event to replay feeds, runs bot decisions, risk-checks non-HOLD orders, optionally submits approved orders, and marks the run complete or failed.

## API And Frontend

API endpoints:

- `GET /evaluation/summary?limit=500`
- `GET /evaluation/replay-runs`
- `GET /evaluation/replay-runs/{run_id}`
- `GET /evaluation/replay-runs/{run_id}/decisions?limit=500&bot_id=...`

Frontend:

- Route: `/eval`
- Navbar label: `Eval`

The Evaluation page shows citation rate, speculative trade rate, unsupported trade rate, fill rate, provider comparison, recent replay runs, and click-through replay decision details with risk/fill/citation columns.

## Testing

Focused tests:

```powershell
pytest -q api/tests/test_evaluation_router.py simulator/tests/test_evaluation.py simulator/tests/test_replay.py
```

These tests use in-memory SQLite and fake decisions/repositories. They do not require API keys or network access.
