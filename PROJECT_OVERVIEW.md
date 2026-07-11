# Market Simulation Platform: Project Overview and Status

Last updated: July 11, 2026

This is the single source of truth for the project. It combines the old project overview and roadmap/status notes into one handoff document.

## Purpose

Market Simulation Platform is an AI trading arena: multiple trading bots compete inside the same simulated market, submit orders into a C++ limit order book, and log their decisions, fills, portfolio state, and evidence.

The project is meant to show three things at once:

- Market structure: limit orders, market orders, price-time priority, fills, liquidity, slippage, portfolios, and PnL.
- Systems engineering: C++ matching engine, Python orchestration, FastAPI service, persistence, Docker scaffolding, and a React dashboard.
- AI engineering: Claude/OpenAI bot personalities, structured decisions, reasoning logs, retrieval-augmented evidence, and a path toward agent tools and evals.

## Current Architecture

```text
         NewsAPI + yfinance + SEC EDGAR
                      |
                      v
        Claude/OpenAI bots + noise traders
                      |
                      v
             Python simulator scheduler
                      |
                      v
          C++ limit order book engine
                      |
                      v
     SQLAlchemy reasoning, portfolio, RAG storage
                      |
                      v
          FastAPI REST + WebSocket API
                      |
                      v
              React/Vite dashboard
```

Main directories:

- `engine/`: C++17 central limit order book, pybind11 bindings, CMake build, benchmark, and engine tests.
- `simulator/`: bot personalities, scheduler, news/price feeds, portfolio accounting, noise traders, reasoning log, and RAG integration.
- `simulator/rag/`: SEC ingestion, document/chunk storage, embeddings, retrieval, and filing monitor.
- `api/`: FastAPI app exposing bots, leaderboard, order book, trades, reasoning, sandbox controls, and WebSocket events.
- `frontend/`: React/Vite/Tailwind dashboard.
- `scripts/`: operational helper scripts, including the SEC ingestion poller.

## Implemented System

### Matching Engine

The C++ engine supports a central limit order book with buy/sell books, price-time priority, limit and market orders, cancellations, trade logs, top-of-book snapshots, depth snapshots, benchmarks, tests, and Python bindings.

If the pybind11 module is not built, the Python `EngineAdapter` runs in stub mode so API/simulator development can continue. Full native matching requires building `engine/`.

### Simulator and Bots

The simulator runs five bot personalities for each provider:

- `BearBot`: pessimistic and sell-biased.
- `DegenBot`: aggressive momentum trader.
- `AnalystBot`: cautious limit-order trader.
- `ContrarianBot`: fades crowded intraday moves.
- `MacroBot`: focuses on macro headlines and macro ETFs.

Each personality can run with Claude and OpenAI, giving ten live competitors. Bots emit structured decisions and fall back to `HOLD` when an LLM call fails.

### API and Frontend

The FastAPI backend exposes health checks, bot summaries, bot details, leaderboard, reasoning, order book snapshots, trades, sandbox controls, and live WebSocket events.

The React frontend has arena, bots, order book, and sandbox pages, with components for bot cards, drawers, decisions, leaderboard stats, live feed, comparison charts, and order book depth.

### Persistence and Reasoning

`ReasoningLog` writes decisions through SQLAlchemy and falls back to local JSONL if the database write fails. Records include bot identity, action, ticker, size, limit price, reasoning, headline, confidence, evidence ids/URLs, fill summary, and portfolio snapshot.

Recent hardening:

- Decision reads return detached plain dictionaries for API safety.
- Portfolio `total_value` snapshots now stay JSON-safe even if mark-to-market pricing fails or returns an unexpected value.

### RAG Evidence Layer

The RAG layer currently supports:

- SQLAlchemy models for documents and chunks.
- Document deduplication by content hash.
- SEC EDGAR ingestion for selected tickers and forms.
- Chunking and optional OpenAI embeddings.
- Raw SEC HTML retention alongside cleaned text.
- Batch embedding updates through a database-backed worker script.
- Optional FAISS vector ranking when `faiss`/`numpy` are installed, with exact cosine fallback.
- Keyword fallback retrieval when embeddings are unavailable.
- Evidence injection into bot prompts.
- Evidence ids/URLs persisted with decisions.
- SEC submissions monitoring for new filings.

## Phase A: Stabilize and Ops

Status: complete.

Completed in this pass:

- Added and hardened `RagRepository.get_latest_accession_for_cik()`.
- Normalized CIK values to canonical 10-digit strings on insert and lookup.
- Wired `monitor.detect_new_filings_for_ciks()` to use the repository latest-accession lookup for automatic deduplication.
- Normalized monitor result keys and SEC lookup calls.
- Added `SEC_USER_AGENT` support for SEC requests, with a project default.
- Added `scripts/ingest_poller.py` as a cron/Windows Task-friendly wrapper around detection and ingestion.
- Added poller logging, unknown-ticker reporting, single-run mode, loop mode, interval control, and graceful Ctrl+C shutdown.
- Added deterministic tests for monitor/dedupe behavior.
- Reworked brittle script-style tests so `pytest -q` runs without live NewsAPI/yfinance calls.

Verification:

```powershell
pytest -q
```

Current result:

```text
33 passed, 1 skipped
```

The skipped test is the optional Python bridge test when the native C++ pybind11 module is not built.

## Current Operational Commands

Run all Python tests:

```powershell
pytest -q
```

Check SEC filings for CIKs:

```powershell
python simulator/rag/monitor.py --ciks 0000320193 --max 5
```

Run the SEC poller once:

```powershell
python scripts/ingest_poller.py --once --tickers AAPL MSFT --db sqlite:///rag.db
```

Run the SEC poller continuously:

```powershell
python scripts/ingest_poller.py --tickers AAPL MSFT NVDA --interval-seconds 3600 --db sqlite:///rag.db
```

Run the embedding worker once:

```powershell
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64
```

Run the embedding worker continuously:

```powershell
python scripts/embed_worker.py --db sqlite:///rag.db --interval-seconds 60 --batch-size 64
```

Suggested Windows Task Scheduler action:

```powershell
python C:\Users\Owner\Desktop\Market-Simulation-Platform\scripts\ingest_poller.py --once --tickers AAPL MSFT NVDA --db sqlite:///C:/Users/Owner/Desktop/Market-Simulation-Platform/rag.db
```

Build the native engine:

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
```

Run the API:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Run the frontend:

```powershell
cd frontend
npm run dev
```

## Current Limitations

- Docker does not yet build the native C++/pybind11 engine in-container.
- Live mode still depends on external API keys and network availability.
- SEC ingestion has retries and metrics, but production deployments should still add persistent job orchestration and alerting.
- Embeddings can run in batches through a DB-backed worker; Redis/RQ or Celery can replace this when distributed workers are needed.
- Vector retrieval uses optional FAISS when installed and falls back to exact cosine search otherwise.
- MCP tools, deterministic risk controls, and historical replay remain future work.

## Roadmap

### Phase B: Improve Ingestion and Indexing

Status: complete as a local production-hardening pass.

Completed:

1. Hardened `simulator/rag/sec_ingestion.py` with retries, exponential backoff, HTTP 429/rate-limit handling, configurable SEC `User-Agent`, and raw HTML retention.
2. Added ingestion metrics: processed, inserted, skipped duplicate, failed fetch, retry count, and last successful accession by CIK.
3. Added batch embedding support through `EmbeddingService.embed_texts()` and repository batch updates.
4. Added `scripts/embed_worker.py`, which treats chunks without embeddings as a database-backed work queue.
5. Added optional FAISS ranking for vector retrieval when `faiss` and `numpy` are installed, with exact cosine fallback when they are not.
6. Added deterministic tests for retry behavior, raw HTML retention, batch embedding, and the embedding worker.

Remaining scale-up option:

- Swap the DB-backed embedding worker for Redis/RQ or Celery when multiple distributed workers are needed.

### Phase C: Agent Tools and Risk Controls

1. Add deterministic `risk_check_order()` before every non-`HOLD` submission.
2. Build a local MCP server exposing market snapshot, portfolio, evidence retrieval, risk limits, and risk check tools.
3. Keep the existing direct prompt path as the default fallback.
4. Add an experimental MCP-backed decision path for one bot, likely `AnalystBot`.

### Phase D: Evaluation and Replay

1. Add retrieval quality checks and evidence citation metrics.
2. Track speculative vs evidence-backed decisions.
3. Add historical replay with an as-of clock and no lookahead bias.
4. Store run configs and compare models on identical replay inputs.
5. Improve frontend evidence views and dashboards.

## Short Handoff

The project now has a working AI trading arena with bot personalities, simulator orchestration, API/frontend surfaces, reasoning persistence, and a hardened local RAG evidence pipeline. Phase A and Phase B are complete and verified. The next engineering focus is Phase C: deterministic risk controls and MCP-style agent tools.
