# Phase D Evaluation And Replay

## Status

Phase D has an initial deterministic foundation.

For the broader project backlog beyond Phase D evaluation/replay, read `.agents/REMAINING_WORK.md`.

Implemented:

- Evidence citation and speculation metrics for logged bot decisions.
- Provider and bot-level comparison helpers.
- Bot behavior analytics for action mix, ticker preferences, confidence trend, risk rejections, fills, and portfolio traces.
- Retrieval quality checks for labeled query/evidence cases.
- Replay run storage for configs, input fingerprints, and per-event bot decisions.
- A replay CLI that runs bots over timestamped JSON events.
- Replay risk checks, optional engine submission, fill summaries, and portfolio snapshots.
- `AsOfRagRepository` to prevent future SEC filings from leaking into historical replay.
- A read-only FastAPI evaluation router.
- A frontend Evaluation page for citation/speculation/unsupported-trade metrics and replay runs.
- Replay run detail endpoints and frontend decision drilldown.
- Evidence chunk lookup by cited ids plus a reusable frontend evidence drawer.
- A frontend Bot Behavior page for live decision analytics.
- Replay comparison reports for runs sharing the same input fingerprint.
- Bundled deterministic replay event fixtures in `data/replay_events/`.

Still future work:

- Model-vs-model replay automation that drives identical events through different model configs.
- Labeled retrieval eval datasets beyond unit-test fixtures.
- Larger real historical market/news datasets beyond the bundled replay fixtures.
- Structured live risk fields in `bot_decisions`; behavior analytics currently infers risk rejections from scheduler reasoning text.

## Evaluation Metrics

Code:

- `simulator/evaluation.py`
- `api/routers/evaluation.py`
- `frontend/src/pages/EvalPage.jsx`

Main helpers:

- `decision_evidence_status(decision)`
- `summarize_decisions(decisions)`
- `compare_model_groups(decisions, group_by="llm_provider")`
- `summarize_bot_behavior(decisions)`
- `get_bot_behavior_detail(decisions)`
- `compare_replay_runs(runs, decisions_by_run)`
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

Replay comparison:

- `ReplayStore.list_runs_by_input_fingerprint(fingerprint)` finds comparable runs.
- `compare_replay_runs()` groups same-input replay results by run, provider, and base bot personality.
- Metrics include decision/trade counts, BUY/SELL/HOLD mix, citation/speculative/unsupported rates, risk rejection rate, fill rate, filled quantity, final replay portfolio value, value change, and max drawdown when snapshots exist.

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
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db
```

Record decisions and risk checks without submitting orders:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db --no-orders
```

Bundled fixtures:

- `data/replay_events/sample_earnings_beat.json`
- `data/replay_events/sample_earnings_miss.json`
- `data/replay_events/sample_fed_rate_shock.json`
- `data/replay_events/sample_market_selloff.json`
- `data/replay_events/sample_sec_filing_risk.json`

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
- `GET /evaluation/bot-behavior?limit=1000`
- `GET /evaluation/bot-behavior/{bot_id}?limit=500`
- `GET /evaluation/evidence?chunk_ids=1,2,3`
- `GET /evaluation/replay-runs`
- `GET /evaluation/replay-runs/compare?fingerprint=...`
- `GET /evaluation/replay-runs/compare?run_id=...`
- `GET /evaluation/replay-runs/{run_id}`
- `GET /evaluation/replay-runs/{run_id}/decisions?limit=500&bot_id=...`

Frontend:

- Route: `/eval`
- Route: `/behavior`
- Navbar label: `Eval`
- Navbar label: `Behavior`

The Evaluation page shows citation rate, speculative trade rate, unsupported trade rate, fill rate, provider comparison, recent replay runs, same-input replay comparison reports, click-through replay decision details with risk/fill/citation columns, and evidence drawer links.

The Behavior page shows per-bot action mix, citation rate, unsupported trade rate, fill rate, risk rejection count, confidence chart, portfolio-value chart, and a decision timeline with evidence drawer links.

## Testing

Focused tests:

```powershell
pytest -q api/tests/test_evaluation_router.py simulator/tests/test_evaluation.py simulator/tests/test_replay.py simulator/tests/test_replay_datasets.py simulator/rag/tests/test_rag_storage.py
```

These tests use in-memory SQLite and fake decisions/repositories. They do not require API keys or network access.
