# Testing And Commands

## Full Verification

```powershell
pytest -q
```

Latest known result:

```text
63 passed, 1 skipped
```

The skipped test is the optional Python bridge test when the native C++ pybind11 module is not built.

## Focused Python Tests

Scheduler and risk:

```powershell
pytest -q simulator/tests/test_scheduler.py simulator/tests/test_risk.py
```

Agent tools:

```powershell
pytest -q simulator/tests/test_agent_tools.py
```

Evaluation and replay:

```powershell
pytest -q api/tests/test_evaluation_router.py simulator/tests/test_evaluation.py simulator/tests/test_replay.py simulator/tests/test_replay_datasets.py simulator/rag/tests/test_rag_storage.py
```

Replay CLI import/argument check:

```powershell
python scripts/run_replay.py --help
```

RAG:

```powershell
pytest -q simulator/rag/tests
```

## SEC/RAG Operations

Check latest SEC filings:

```powershell
python simulator/rag/monitor.py --ciks 0000320193 --max 5
```

Poll and ingest once:

```powershell
python scripts/ingest_poller.py --once --tickers AAPL MSFT NVDA --db sqlite:///rag.db
```

Poll continuously:

```powershell
python scripts/ingest_poller.py --tickers AAPL MSFT NVDA --interval-seconds 3600 --db sqlite:///rag.db
```

Embed missing chunks once:

```powershell
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64
```

Embed continuously:

```powershell
python scripts/embed_worker.py --db sqlite:///rag.db --interval-seconds 60 --batch-size 64
```

## Agent Tools

Run local MCP-style server:

```powershell
python scripts/agent_mcp_server.py --db sqlite:///rag.db
```

Enable AnalystBot tool path:

```powershell
$env:ANALYST_AGENT_TOOLS_ENABLED="true"
```

Disable it:

```powershell
$env:ANALYST_AGENT_TOOLS_ENABLED="false"
```

## Historical Replay

Run replay events and submit approved orders:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db
```

Run decisions/risk checks only:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db --no-orders
```

Bundled replay fixtures:

```text
data/replay_events/sample_earnings_beat.json
data/replay_events/sample_earnings_miss.json
data/replay_events/sample_fed_rate_shock.json
data/replay_events/sample_market_selloff.json
data/replay_events/sample_sec_filing_risk.json
```

## API And Frontend

Run API:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Evaluation endpoints:

```text
GET http://localhost:8000/evaluation/summary?limit=500
GET http://localhost:8000/evaluation/bot-behavior?limit=1000
GET http://localhost:8000/evaluation/bot-behavior/{bot_id}?limit=500
GET http://localhost:8000/evaluation/evidence?chunk_ids=1,2,3
GET http://localhost:8000/evaluation/replay-runs
GET http://localhost:8000/evaluation/replay-runs/compare?fingerprint={input_fingerprint}
GET http://localhost:8000/evaluation/replay-runs/compare?run_id={run_id}
GET http://localhost:8000/evaluation/replay-runs/{run_id}
GET http://localhost:8000/evaluation/replay-runs/{run_id}/decisions
```

Run frontend:

```powershell
cd frontend
npm run dev
```

Open the Evaluation page:

```text
http://localhost:5173/eval
```

Open the Behavior page:

```text
http://localhost:5173/behavior
```

## Native Engine

Build:

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
```

If the native module is missing, `EngineAdapter` runs in stub mode. This keeps API/simulator development possible but does not provide full matching behavior.

## Test Design Rules

- Mock LLMs.
- Mock network.
- Keep tests deterministic.
- Use in-memory SQLite where possible.
- Do not require `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `NEWS_API_KEY`, yfinance, or live SEC access.
