# Historical Event Builder

Date: 2026-08-18

Agent: Codex

Task: Start Phase 1 by implementing the historical replay event builder and
keeping the playbook current.

## Summary

Completed the first implementation slice for six-month replay data generation.

- Added `scripts/build_historical_replay_events.py`.
- Added daily replay event generation from yfinance, local price JSON, or
  existing replay event JSON used as a smoke-test price source.
- Added local timestamped `--news-file` support for historical headlines/events.
- Added `historical-first`, `news-file`, `synthetic`, and `price-only` modes.
- Added benchmark prices/returns, deterministic market regime features,
  per-ticker generated features, source metadata, and no-lookahead headline
  checks.
- Added companion quality reports with dataset grade, headline coverage,
  missing price counts, duplicate timestamp counts, and no-lookahead violation
  counts.
- Allowed safe replay event paths under `data/replay_events/generated/`.
- Reconciled documented parser/outcome/evaluation-scheduler behavior with tests.

## Files Changed

- `scripts/build_historical_replay_events.py`
- `simulator/tests/test_historical_replay_event_builder.py`
- `simulator/replay_workflow.py`
- `api/routers/evaluation.py`
- `simulator/config.py`
- `simulator/bots/macro_bot.py`
- `simulator/base_bot.py`
- `simulator/reasoning_log.py`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/session_notes/2026-08-18_historical_event_builder.md`

## Commands Run

```powershell
python -m py_compile scripts/build_historical_replay_events.py simulator/replay_workflow.py api/routers/evaluation.py
pytest -q simulator/tests/test_historical_replay_event_builder.py simulator/tests/test_replay_datasets.py api/tests/test_evaluation_router.py -q
python scripts/build_historical_replay_events.py --start 2026-01-28 --end 2026-01-29 --tickers MSFT AAPL SPY --benchmarks SPY --price-file data/replay_events/sample_earnings_beat.json --news-mode synthetic --output "$env:TEMP\historical_replay_builder_smoke.json" --report "$env:TEMP\historical_replay_builder_smoke.report.json"
pytest -q
```

## Results

- Tests: `210 passed, 1 skipped`.
- Build: not applicable; frontend was not changed.
- Data artifacts: CLI smoke wrote temp files under `$env:TEMP`.
- Replay run IDs: none; no model-provider replay was run.
- Input fingerprints: none.

## Design Decisions

- Used yfinance for the first live historical price adapter because the project
  already uses it.
- Added local price-file support so future agents can run deterministic builds
  without network access.
- Added existing replay-event JSON as a price input path so bundled fixtures can
  smoke-test the CLI.
- Chose a local timestamped `--news-file` adapter as the minimum viable
  historical news/event source path. This lets a future provider export, SEC/RAG
  event export, or calendar export plug in without changing replay schema.
- Kept synthetic OHLCV-derived summaries as a fallback and labeled them
  explicitly so they are not mistaken for real historical news.
- Tightened replay validation to reject non-increasing event timestamps.

## Risks Or Caveats

- A true historical news/calendar/SEC source has not been populated yet.
- Synthetic-only generated datasets are useful for plumbing but should not drive
  ML conclusions or agent pruning.
- The first one-month pilot still needs a real timestamped `--news-file` if it
  is to be called decision-grade.
- Replay resume/idempotency is still not implemented.

## Next Recommended Task

- Build `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`
  with real timestamped `--news-file` context if possible, inspect the report,
  and only then run a no-orders replay matrix.

## Open Questions

- Which historical headline/calendar/SEC export should supply the first
  `--news-file`?
- What minimum real-headline coverage threshold should be required before the
  one-month pilot is considered decision-grade?
