# Market Simulation Platform

AI Trading Arena is a capital markets demo project: ten LLM-powered trading bots compete in a simulated market using a custom C++ limit order book.

The project is built to demonstrate:

- market structure knowledge: limit orders, market orders, price-time priority, fills, liquidity, and PnL;
- systems engineering: C++ engine, Python orchestration, FastAPI, persistence, and a React dashboard;
- AI engineering: model-vs-model agents, personality prompts, structured decisions, reasoning logs, RAG evidence, and a roadmap toward MCP, risk controls, and evals.

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
      SQLAlchemy reasoning/PnL log
                     |
                     v
       FastAPI REST + WebSocket API
                     |
                     v
          React/Vite dashboard
```

Main directories:

- `engine/`: C++17 matching engine, CMake build, pybind11 bindings, benchmark, and engine tests.
- `simulator/`: bot personalities, scheduler, news/price feeds, portfolios, noise traders, and decision persistence.
- `api/`: FastAPI app exposing bots, leaderboard, order book, trades, reasoning, sandbox, and WebSocket events.
- `frontend/`: React/Vite/Tailwind dashboard.
- `PROJECT_OVERVIEW.md`: merged project overview, current status, and roadmap.

## Bot Competition

The live arena creates five trading personalities for each LLM provider:

- BearBot: pessimistic sell-biased trader.
- DegenBot: aggressive momentum trader.
- AnalystBot: cautious limit-order trader.
- ContrarianBot: fades crowded intraday moves.
- MacroBot: trades macro ETFs from macro headlines.

Each personality runs once with Claude and once with OpenAI, giving ten live competitors.

## Requirements

Recommended local tools:

- Python 3.11 or 3.12
- CMake 3.20+
- A C++17 compiler
- Node.js 20+
- PostgreSQL for full live mode, or SQLite for focused tests/sandbox work

Python packages are listed in `requirements.txt`.

Frontend packages are listed in `frontend/package.json`.

## Environment

Copy `.env.example` to `.env` in the project root:

```powershell
Copy-Item .env.example .env
```

Required for full live mode:

```text
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
NEWS_API_KEY=your_newsapi_key_here
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
DATABASE_URL=postgresql://user:password@localhost:5432/marketsim
ARENA_API_KEY=local-demo-key
```

Notes:

- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `NEWS_API_KEY` are needed for live LLM/news runs.
- `SEC_USER_AGENT` is used for SEC EDGAR requests; set it to a descriptive app/contact string before live polling.
- `DATABASE_URL` is required by the API startup path.
- `ARENA_API_KEY` protects write endpoints such as sandbox start/stop.
- The frontend reads `VITE_API_URL`; see `frontend/.env.example`.

For local development, you can use SQLite for non-live experiments and tests by passing an explicit SQLite URL where supported. The main API currently expects `DATABASE_URL` to be configured.

## Install

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

## Build the C++ Engine

From the repo root:

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
```

The Python code looks for the compiled pybind11 module under:

```text
engine/build/Debug
```

If the module is not found, the Python `EngineAdapter` can run in stub mode, but the full demo needs the C++ extension built.

## Run the API

From the repo root:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Useful URLs:

- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- WebSocket stream: `ws://localhost:8000/ws/live`

## Run the Frontend

In another terminal:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

The Docker Compose frontend service uses port `3000`; Vite local dev defaults to `5173`.

## Run with Docker Compose

The repo includes simple Dockerfiles for the API and frontend:

```powershell
docker compose up --build
```

Important:

- Docker mode still needs a valid `.env`.
- The API container installs Python dependencies and starts FastAPI.
- The current Docker setup does not compile the C++ extension inside the container; build the engine locally for the full native engine path, or expect Python stub-mode behavior until containerized engine builds are added.

## Tests

Python tests:

```powershell
python -m pytest simulator/tests engine/tests/test_python_bridge.py
```

C++ tests:

```powershell
cmake --build engine/build --config Debug
ctest --test-dir engine/build --output-on-failure -C Debug
```

Frontend build check:

```powershell
cd frontend
npm run build
```

RAG embedding worker:

```powershell
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64
```

## Demo Script

Use this flow when presenting the project:

1. Explain the goal: Claude vs OpenAI trading agents compete inside a custom market simulation.
2. Show `engine/` and describe price-time priority, market/limit orders, cancellations, and fills.
3. Show the five bot personality classes in `simulator/bots/`.
4. Start the API and frontend.
5. Open the arena dashboard and leaderboard.
6. Open a bot drawer or reasoning endpoint to show structured decisions and PnL.
7. Show the order book page to connect LLM decisions to market mechanics.
8. Explain the roadmap: stronger ingestion/indexing, MCP tools, deterministic risk checks, evals, and historical replay.

Short interview pitch:

```text
I built an AI trading arena where Claude and OpenAI compete as trading agents.
The agents read market data and news, produce structured trade decisions, and
submit orders into my own C++ limit order book. The platform logs reasoning,
fills, and portfolio state so I can compare model behavior and profitability.
The next phase hardens RAG ingestion/indexing, then adds MCP tool use,
deterministic risk controls, and evals.
```

## Known Limitations

- RAG ingestion now has retries, raw HTML retention, metrics, batch embedding support, and optional FAISS ranking.
- Distributed embedding workers are not wired yet; the current worker uses the database as a simple local queue.
- MCP is not implemented yet.
- Risk controls are still basic and should be made deterministic before trusting LLM-submitted orders.
- Clean Docker support for compiling the C++ pybind11 extension is not finished.
- Live demos depend on external APIs and valid keys.
- Historical replay/backtesting is planned but not implemented.

See `PROJECT_OVERVIEW.md` for the full implementation plan.
