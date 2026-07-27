# Replay Event Fixtures

These small deterministic fixtures make replay usable without live market or
news data.

Run one fixture:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db --no-orders
```

Run the same fixture with different provider/bot settings to create comparable
runs. Runs created from the same event JSON share an `input_fingerprint`, so
`/evaluation/replay-runs/compare` can compare them fairly.

Run a small same-input provider matrix:

```powershell
python scripts/run_replay_matrix.py --events data/replay_events/sample_ai_infrastructure_cycle.json --provider-sets claude openai --no-orders
```

Run every bundled fixture and write a suite report:

```powershell
python scripts/run_replay_matrix.py --provider-sets claude openai --no-orders --report data/replay_runs/matrix_report.json
```

## Schema

Each file is a JSON object:

- `name`: replay run name fallback.
- `description`: short scenario summary.
- `config`: metadata stored on the replay run.
- `events`: ordered list of replay events.

Each event should include:

- `timestamp` or `as_of_time`: ISO timestamp.
- `prices`: ticker-to-price map.
- `ohlcv`: optional ticker-to-market-data map.
- `trending_headlines`: broad market headlines.
- `recent_headlines`: newest general headlines.
- `ticker_headlines`: ticker-specific headline lists.
- `expected_notes`: optional notes for humans reviewing the replay.

Design rules:

- No network access is required.
- Event order is deterministic.
- Prices are synthetic but plausible.
- Headlines are fixture text, not live news.
- The SEC filing risk fixture is intended to exercise no-lookahead RAG when the
  database contains filings before and after the event timestamps.
- The liquidity rotation fixture is intended to exercise risk discipline across
  bank stress, energy defensiveness, and quality-growth recovery.
