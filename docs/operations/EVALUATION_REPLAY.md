# Evaluation And Replay Workflow

This workflow turns live bot activity into labeled data, then uses replay to
compare agents on identical market inputs.

## 1. Collect Live Decisions

Run the API and scheduler with the normal app settings. Each bot decision writes:

- public rationale, action, ticker, quantity, confidence, and evidence ids
- fill summary and portfolio snapshot
- provider/model metadata and estimated LLM cost
- immediate outcome rows for holds, fills, pending orders, risk rejections, and
  execution errors

## 2. Label Outcomes

Outcome labeling is scheduled by the API process when
`EVALUATION_SCHEDULER_ENABLED=true` and `OUTCOME_LABELING_ENABLED=true`. The
default cadence is every 60 minutes, after a 60 second startup delay:

```env
EVALUATION_SCHEDULER_ENABLED=true
OUTCOME_LABELING_ENABLED=true
OUTCOME_LABELING_INTERVAL_MINS=60
OUTCOME_LABELING_HORIZONS=1h,6h,1d,7d
OUTCOME_LABELING_DECISION_LIMIT=2000
```

You can still create due horizon labels manually:

```powershell
python scripts/update_decision_outcomes.py --db sqlite:///marketsim.db --horizons 1h,6h,1d,7d --limit 2000
```

For hosted deployments, call the protected endpoint with `ARENA_API_KEY`:

```powershell
Invoke-RestMethod "https://your-api-domain.example/evaluation/outcomes/update" `
  -Method Post `
  -Headers @{ "X-API-Key" = $env:ARENA_API_KEY } `
  -ContentType "application/json" `
  -Body '{"horizons":["1h","6h","1d","7d"],"decision_limit":2000}'
```

Outcome labels are available at:

- `GET /ops/evaluation/status`
- `GET /evaluation/outcomes/summary?horizon=1h`
- `GET /evaluation/outcomes/recent?horizon=1h`

## 3. Generate The Live Report

The weekly report reads stored live decisions and outcome labels only. It does
not call Claude or OpenAI. It is marked `monitoring_only` until the selected
horizon has at least 50 labeled decisions by default; benchmark and replay
comparisons remain explicitly data-limited until their snapshots are stored.

The API and Evaluation page expose the current window:

```powershell
Invoke-RestMethod "http://localhost:8000/evaluation/live-report?horizon=1d&period_days=7&min_samples=50"
```

Generate Markdown and JSON files locally:

```powershell
python scripts/run_weekly_evaluation_report.py `
  --db sqlite:///marketsim.db `
  --horizon 1d `
  --period-days 7 `
  --min-samples 50 `
  --output-dir data/live_evaluation
```

The API process schedules this report weekly by default. Override the cadence
or output location with:

```env
LIVE_EVALUATION_REPORT_ENABLED=true
LIVE_EVALUATION_REPORT_INTERVAL_HOURS=168
LIVE_EVALUATION_REPORT_STARTUP_DELAY_SECS=120
LIVE_EVALUATION_REPORT_LOOKBACK_DAYS=7
LIVE_EVALUATION_REPORT_MIN_SAMPLES=50
LIVE_EVALUATION_REPORT_DECISION_LIMIT=10000
LIVE_EVALUATION_REPORT_HORIZON=1d
LIVE_EVALUATION_REPORT_DIR=data/live_evaluation
```

## 4. Run Replay Fixtures

Replay matrices are scheduler-ready, but disabled by default because each run
can call live model providers. Turn them on only when you want the hosted app to
spend budget on scheduled replay:

```env
REPLAY_MATRIX_SCHEDULE_ENABLED=true
REPLAY_MATRIX_INTERVAL_HOURS=24
REPLAY_MATRIX_STARTUP_DELAY_SECS=300
REPLAY_MATRIX_FIXTURES=sample_earnings_beat.json
REPLAY_MATRIX_PROVIDER_SETS=claude,openai
REPLAY_MATRIX_BOTS=analyst,bear,macro
REPLAY_MATRIX_EXECUTE_ORDERS=false
REPLAY_MATRIX_MAX_FIXTURES_PER_RUN=1
```

The default provider set runs Claude and OpenAI separately against the same
fixture, which gives `/eval` same-input comparison rows without multiplying
fixtures.

List bundled fixtures:

```powershell
Invoke-RestMethod "http://localhost:8000/evaluation/replay-fixtures"
```

Run one fixture:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --providers claude,openai --bots analyst,bear,macro --db sqlite:///replay.db --no-orders
```

Run a same-input matrix:

```powershell
python scripts/run_replay_matrix.py --events data/replay_events/sample_ai_infrastructure_cycle.json --provider-sets claude openai --bots analyst,bear,macro --db sqlite:///replay.db --no-orders --report data/replay_runs/ai_infra_matrix_report.json
```

Replay runs with the same event JSON share an `input_fingerprint`, so the API
can compare them fairly:

```powershell
Invoke-RestMethod "http://localhost:8000/evaluation/replay-runs/compare?run_id=<run-id>"
```

## 5. Choose The Next Agent Set

Use `/eval` to compare:

- citation rate and unsupported trade rate
- risk rejection rate
- fill rate
- win rate by outcome horizon
- PnL after estimated LLM cost
- replay performance on the same input fingerprint

The next six-agent set should be chosen only after there are enough live and
replay outcome rows to compare agent/provider/prompt behavior.
