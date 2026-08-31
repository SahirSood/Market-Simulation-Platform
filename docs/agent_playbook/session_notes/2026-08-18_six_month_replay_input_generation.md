# Six-Month Replay Input Generation

Date: 2026-08-18

Agent: Codex

Task: Generate and inspect replay input artifacts through the six-month quality
report, then stop before running paid/large model replays.

## Summary

Generated the first real-price replay inputs for the six-month data program.

- Added official macro-calendar context for 2026-02-18 through 2026-08-18.
- Generated the one-month pilot replay input and quality report.
- Generated the six-month daily replay input and quality report.
- Verified the six-month generated file loads through the replay workflow.
- Ran the replay matrix runner in dry-run mode only to prove the planned replay
  commands exist.
- Patched the replay fixture scanner so support/source JSON files in the
  generated folder are ignored instead of surfaced as invalid replay fixtures.
- Did not run actual model-provider replay calls.

## Files Changed

- `data/replay_events/generated/historical_macro_context_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`
- `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
- `api/routers/evaluation.py`
- `api/tests/test_evaluation_router.py`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/session_notes/2026-08-18_six_month_replay_input_generation.md`

## Commands Run

```powershell
python -m json.tool data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json > $null
```

```powershell
python scripts\build_historical_replay_events.py --start 2026-07-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL TSLA SPY QQQ TLT GLD IEF --benchmarks SPY QQQ TLT GLD --frequency 1d --news-mode historical-first --news-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --output data\replay_events\generated\one_month_pilot_2026-07-18_2026-08-18.json --report data\replay_events\generated\one_month_pilot_2026-07-18_2026-08-18.report.json
```

```powershell
python scripts\build_historical_replay_events.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL TSLA SPY QQQ TLT GLD IEF --benchmarks SPY QQQ TLT GLD --frequency 1d --news-mode historical-first --news-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --output data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.json --report data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.report.json
```

```powershell
python scripts\run_replay_matrix.py --events data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --dry-run --report data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json
```

```powershell
python -c "import sys; sys.path.insert(0, 'simulator'); from replay_workflow import load_replay_event_file; name, config, events=load_replay_event_file('generated/six_month_daily_2026-02-18_2026-08-18.json'); print(name); print(config.get('dataset_grade')); print(len(events)); print(events[0]['timestamp']); print(events[-1]['timestamp'])"
```

```powershell
pytest -q api\tests\test_evaluation_router.py::test_list_replay_fixtures_summarizes_available_scenarios simulator\tests\test_historical_replay_event_builder.py -q
```

```powershell
python -c "import sys; sys.path[:0]=['simulator','.']; from api.routers import evaluation as e; r=e._load_replay_fixtures(); generated=[f['file_name'] for f in r['fixtures'] if f['file_name'].startswith('generated/')]; print({'fixture_count': len(r['fixtures']), 'error_count': len(r['errors']), 'generated': generated})"
```

```powershell
pytest -q
```

## Results

One-month pilot:

- File: `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`
- Report: `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.report.json`
- Events: 22 market days.
- Price source: yfinance.
- Dataset grade: `mixed_real_and_synthetic_context`.
- Headline appearances: 42 real, 206 synthetic.
- Real-context days: 6.
- Synthetic-only days: 16.
- Missing prices: 0.
- Duplicate timestamps: 0.
- No-lookahead violations: 0.

Six-month daily input:

- File: `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json`
- Report: `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.report.json`
- Events: 126 market days.
- Price source: yfinance.
- Dataset grade: `mixed_real_and_synthetic_context`.
- Headline appearances: 238 real, 1,209 synthetic.
- Real-context days: 33.
- Synthetic-only days: 93.
- Missing prices: 0.
- Duplicate timestamps: 0.
- No-lookahead violations: 0.

Replay dry run:

- Report:
  `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
- Planned commands: 2.
- Provider sets: `claude`, `openai`.
- Bots: `analyst,bear,macro`.
- Execution mode: `--no-orders`.
- Actual model calls: 0.

Fixture library verification:

- Focused tests: 5 passed.
- Full Python suite: `210 passed, 1 skipped`.
- Local fixture scan: 9 fixtures, 0 errors.
- Generated fixtures listed:
  - `generated/one_month_pilot_2026-07-18_2026-08-18.json`
  - `generated/six_month_daily_2026-02-18_2026-08-18.json`
- Macro context source file is ignored as support data, not listed as a broken
  replay fixture.

## Design Decisions

- Used official macro-calendar events from Federal Reserve, BLS, and BEA as the
  first timestamped real context source.
- Used yfinance for daily OHLCV because the builder already supports it and it
  avoids introducing a paid market-data dependency.
- Kept synthetic fallback enabled through `historical-first` mode so every event
  has enough prompt context while still marking synthetic rows clearly.
- Stopped before running actual replay/model-provider calls because no provider
  keys were visible in the process and the generated context is not yet
  decision-grade.

## Risks Or Caveats

- The generated files are valid replay inputs, but they are not a true
  historical news dataset.
- Real context is macro-calendar only; ticker-specific company headlines,
  earnings, and SEC/RAG event context are still missing.
- The report headline counts are section appearances, not unique real source
  events.
- `events_below_min_headline_coverage` is 0 because synthetic fallback filled
  gaps. It does not mean the file has full real-news coverage.
- Replay resume/idempotency is still missing, so large replay runs should not be
  treated as safely resumable yet.

## Next Recommended Task

- Either run the one-month no-orders replay matrix as a plumbing pilot, or first
  enrich `historical_macro_context_2026-02-18_2026-08-18.json` with
  timestamped ticker-specific historical headlines, SEC/RAG filings, and
  earnings events.
- Add resume/skip/chunk controls before running the full six-month matrix.

## Open Questions

- Is macro-calendar plus synthetic context acceptable for the first no-orders
  pilot?
- What minimum real-context coverage threshold makes the six-month dataset
  decision-grade enough for ML and agent pruning?
