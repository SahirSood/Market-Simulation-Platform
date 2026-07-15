# Testing And Commands

## Full Verification

```powershell
pytest -q
```

Latest known result:

```text
41 passed, 1 skipped
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

## API And Frontend

Run API:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Run frontend:

```powershell
cd frontend
npm run dev
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
