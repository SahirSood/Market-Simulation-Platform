# Market Simulation Platform

Market Simulation Platform is an AI trading arena. Claude and OpenAI run the
same five trading personalities inside the same simulated market, read the same
prices and evidence, pass through the same deterministic risk controls, and
submit orders into the same custom C++ limit order book.

The project is designed to demonstrate three things together:

- Market structure: limit orders, market orders, price-time priority, fills,
  liquidity, positions, shorts, and PnL.
- Systems engineering: a native C++ engine, Python orchestration, FastAPI,
  SQLAlchemy persistence, Docker packaging, and a React dashboard.
- AI engineering: structured model decisions, RAG evidence, safe agent-tool
  access, replay-based evaluation, and public-safe observability.

The deployment target is a public, read-only showcase. Visitors can inspect
results, evidence, and metrics, but cannot trigger protected writes.

**Live demo:** [market-sim-frontend.onrender.com](https://market-sim-frontend.onrender.com/?utm_source=github&utm_medium=repo&utm_campaign=market_sim_showcase)

## Dashboard Preview

These are selected views from the public read-only dashboard.

### Overview Benchmark

<img src="docs/assets/dashboard-overview.jpg" alt="Overview dashboard showing the model trading benchmark" width="960" />

The homepage compares Claude and OpenAI on identical market inputs, highlights
the current leader, and makes the fairness of the benchmark visible at a glance.

### Order Book

<img src="docs/assets/order-book.jpg" alt="Order book page showing bids, asks, midpoint, and spread" width="960" />

This view connects model decisions to actual market mechanics: bids, asks,
midpoint, spread, and queued liquidity inside the simulated market.

### Behavior Analytics

<img src="docs/assets/bot-behavior.jpg" alt="Behavior page showing action mix, confidence, citations, and portfolio value" width="960" />

The behavior page focuses on how the bots act over time, including action mix,
confidence, citation quality, fills, risk rejections, and portfolio traces.

### Research And Evidence

<img src="docs/assets/research-tab.jpg" alt="Research page showing ingested SEC filings, chunks, embeddings, and recall metrics" width="960" />

The research page shows the RAG layer behind the decisions: ingested SEC
filings, chunking, embeddings, duplicate handling, and retrieval quality.

## Architecture

```mermaid
flowchart LR
    subgraph Inputs
        Prices[Market prices]
        News[News headlines]
        SEC[SEC filings]
    end

    subgraph Intelligence
        Bots[Claude and OpenAI bots]
        RAG[RAG repository]
        MCP[MCP-style tools]
    end

    subgraph Control
        Scheduler[Python scheduler]
        Risk[Deterministic risk gate]
        Engine[C++ order book]
        Portfolio[Portfolio accounting]
    end

    subgraph Product
        DB[Decision and replay storage]
        API[FastAPI REST and WebSocket API]
        UI[React dashboard]
    end

    SEC --> RAG
    Prices --> Bots
    News --> Bots
    RAG --> Bots
    MCP -. optional tool path .-> Bots
    RAG --> MCP
    Prices --> MCP
    Portfolio --> MCP
    Risk --> MCP
    Bots --> Scheduler
    Scheduler --> Risk
    Risk -->|approved| Engine
    Risk -->|rejected| DB
    Engine --> Portfolio
    Portfolio --> DB
    Bots --> DB
    RAG --> DB
    DB --> API
    Engine --> API
    API --> UI
```

The key boundary is the risk gate: models can suggest actions, but only
deterministic scheduler code can authorize submission to the matching engine.

<details>
<summary><strong>One Decision, End To End</strong></summary>

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant B as Bot
    participant R as RAG
    participant L as Claude or OpenAI
    participant G as Risk gate
    participant E as C++ engine
    participant D as Database
    participant U as UI

    S->>B: Start decision cycle
    B->>R: Retrieve filing evidence
    R-->>B: Chunk ids and text snippets
    B->>L: Ask for structured BUY, SELL, or HOLD
    L-->>B: JSON decision
    B-->>S: Normalized decision
    S->>G: Enforce deterministic limits
    alt Rejected
        G-->>S: Rejection reason
        S->>D: Persist rejected decision
        S->>U: Publish safe activity event
    else Approved
        G-->>S: Approved
        S->>E: Submit order
        E-->>S: Order id and fills
        S->>D: Persist order, fills, and portfolio snapshot
        S->>U: Publish decision and trade event
    end
```

</details>

<details>
<summary><strong>MCP And RAG Flow</strong></summary>

```mermaid
flowchart TD
    Client[AnalystBot or local client] --> Host[AgentMcpAdapter]
    Host --> Policy[Auth, filters, approvals, trace metadata]
    Policy --> Server[MarketAgentToolServer]

    Server --> Market[market_snapshot]
    Server --> PortfolioTool[portfolio_snapshot]
    Server --> Evidence[retrieve_evidence]
    Server --> Limits[risk_limits]
    Server --> Preflight[risk_check_order]

    Market --> PriceFeed[Price feed]
    PortfolioTool --> Portfolios[Bot portfolios]
    Evidence --> Repo[RagRepository]
    Repo --> FilingChunks[SEC filing chunks]
    Limits --> SharedLimits[Shared RiskLimits]
    Preflight --> RiskCode[Deterministic risk code]

    Host --> Traces[Safe activity traces]
    Host --> Audit[Protected audit rows]
```

The tool layer is advisory. The scheduler repeats the real deterministic risk
check before execution, so MCP access cannot bypass the final safety boundary.

</details>

<details>
<summary><strong>RAG Pipeline</strong></summary>

```mermaid
flowchart LR
    Poller[SEC poller] --> Detect[Find new filings]
    Detect --> Fetch[Fetch 10-K, 10-Q, and 8-K HTML]
    Fetch --> Clean[Normalize text]
    Clean --> Dedupe[Deduplicate by accession, URL, then hash]
    Dedupe --> Chunk[Create bounded chunks]
    Chunk --> Embed[Generate embeddings]
    Embed --> Store[Store documents and chunks]
    Store --> Retrieve[Vector search with keyword fallback]
    Retrieve --> Prompt[Send evidence into bot prompt]
    Prompt --> Persist[Persist cited chunk ids and source URLs]
```

</details>

## Product Highlights

- Ten live competitors: five fixed trading personalities, each run once on
  Claude and once on OpenAI.
- C++17 matching engine with pybind11 bindings and a Python stub fallback.
- Deterministic scheduler-level risk checks before every non-`HOLD` order.
- SEC filing ingestion, chunking, embeddings, retrieval, and no-lookahead replay
  filtering.
- Local MCP-style tool layer for market, portfolio, evidence, and risk access.
- Evaluation surfaces for behavior, citations, retrieval quality, replay runs,
  and same-input model comparisons.
- Public-safe telemetry that avoids secrets, hidden chain-of-thought, raw
  prompts, and raw tool arguments.

## Repository Layout

- `engine/`: C++17 matching engine, pybind11 bindings, benchmark, and tests.
- `simulator/`: bots, scheduler, risk logic, portfolios, RAG, evaluation, and
  replay helpers.
- `simulator/rag/`: SEC ingestion, storage models, embeddings, retrieval, and
  monitor logic.
- `api/`: FastAPI application, routers, app state, and WebSocket support.
- `frontend/`: React/Vite/Tailwind dashboard.
- `scripts/`: ingestion, embedding, replay, retrieval, MCP, smoke, and ops
  utilities.
- `docs/`: public architecture and operations docs.

## Environment

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Common variables:

```text
OPENAI_API_KEY=your_openai_key_here
OPENAI_PROJECT_ID=proj_your_project_id_here
ANTHROPIC_API_KEY=your_anthropic_key_here
NEWS_API_KEY=your_newsapi_key_here
SEC_USER_AGENT=MarketSimulationPlatform/1.0 your_email@example.com
DATABASE_URL=postgresql://user:password@localhost:5432/marketsim
ARENA_API_KEY=local-demo-key
STARTING_CASH=100000
PUBLIC_READ_ONLY_MODE=true
SANDBOX_ENABLED=false
ENGINE_NATIVE_REQUIRED=false
OPENAI_MODEL=gpt-5.4-mini
CLAUDE_MODEL=claude-sonnet-5
OPENAI_REASONING_EFFORT=medium
CLAUDE_EFFORT=medium
LLM_MAX_TOKENS=800
LLM_MONTHLY_SPEND_LIMIT_USD=20
SHORT_SELLING_ENABLED=true
```

Notes:

- `DATABASE_URL` is required by the API startup path.
- `OPENAI_API_KEY` is needed for OpenAI decisions and optional embeddings.
- `ANTHROPIC_API_KEY` enables Claude decisions; without it, Claude bots fall
  back to `HOLD`.
- `SEC_USER_AGENT` should be set before live SEC polling.
- `ARENA_API_KEY` protects replay, ops, and other write endpoints.
- The frontend reads `VITE_API_URL`; see `frontend/.env.example`.

## Local Setup

Install Python dependencies:

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

Build the native engine:

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
```

If the native module is missing, the Python adapter can run in stub mode, but
the full demo experience expects the C++ extension to be present.

## Run The App

Start the API:

```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Start the frontend:

```powershell
cd frontend
npm run dev
```

Useful local URLs:

- API health: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/ready`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

## Docker

Run the stack with Docker Compose:

```powershell
docker compose up --build
```

The API image uses a builder/runtime split and smoke-checks the native engine.
The frontend image builds static Vite assets and serves them with nginx.

## Deployment

`render.yaml` is the configured first deployment path. It provisions:

- `market-sim-api`
- `market-sim-frontend`
- `market-sim-db`

Render wires `DATABASE_URL`, `FRONTEND_URL`, and `VITE_API_URL`, generates
`ARENA_API_KEY`, and keeps the app in a public read-only posture. Full details
are in [docs/operations/DEPLOYMENT.md](docs/operations/DEPLOYMENT.md).

## Verification

Run the Python test suite:

```powershell
pytest -q
```

Latest verified result: `180 passed, 1 skipped`.

Build the frontend:

```powershell
cd frontend
npm run build
```

Run the release smoke checklist:

```powershell
Get-Content docs/operations/RELEASE.md
```

Useful focused commands:

```powershell
python scripts/container_smoke.py --require-native
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64 --max-retries 1
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db --no-orders
python scripts/run_replay_matrix.py --events data/replay_events/sample_ai_infrastructure_cycle.json --provider-sets claude openai --no-orders
```

## Public Docs

- [Documentation Index](docs/README.md)
- [MCP And Agent Integration](docs/architecture/MCP.md)
- [Deployment Runbook](docs/operations/DEPLOYMENT.md)
- [Release And Smoke Checklist](docs/operations/RELEASE.md)

## Known Limitations

- The MCP-style server is local-only unless a concrete external client requires
  a fuller remote protocol implementation.
- Risk controls are deterministic and intentionally simpler than real brokerage
  or prime-broker risk systems.
- Open resting orders are recorded in the ledger but are not rehydrated into
  the in-memory C++ books after restart.
- Larger audited historical datasets remain future work beyond the bundled
  replay and retrieval fixtures.

The publishable architecture and operations story now lives in this README plus
the public docs under `docs/`.
