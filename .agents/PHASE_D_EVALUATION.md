# Phase D Evaluation And Replay

## Status

Phase D has an initial deterministic foundation.

Implemented:

- Evidence citation and speculation metrics for logged bot decisions.
- Provider and bot-level comparison helpers.
- Retrieval quality checks for labeled query/evidence cases.
- Replay run storage for configs, input fingerprints, and per-event bot decisions.
- `AsOfRagRepository` to prevent future SEC filings from leaking into historical replay.
- A read-only FastAPI evaluation router.
- A frontend Evaluation page for citation/speculation/unsupported-trade metrics and replay runs.

Still future work:

- Full replay CLI over historical market/news datasets.
- Model-vs-model replay automation that drives identical events through different model configs.
- Frontend drill-down from metrics into exact decisions and evidence snippets.
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

## API And Frontend

API endpoints:

- `GET /evaluation/summary?limit=500`
- `GET /evaluation/replay-runs`

Frontend:

- Route: `/eval`
- Navbar label: `Eval`

The Evaluation page shows citation rate, speculative trade rate, unsupported trade rate, fill rate, provider comparison, and recent replay runs.

## Testing

Focused tests:

```powershell
pytest -q simulator/tests/test_evaluation.py simulator/tests/test_replay.py
```

These tests use in-memory SQLite and fake decisions/repositories. They do not require API keys or network access.
