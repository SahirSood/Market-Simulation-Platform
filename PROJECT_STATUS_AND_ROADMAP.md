# Market Simulation Platform: Status and Roadmap

Last reviewed: July 9, 2026

## Project Purpose

This project is an AI-heavy capital markets demo for a QTS capital markets role. The goal is to prove capability across three areas at once:

- Trading market structure: limit order books, market orders, limit orders, price-time priority, fills, portfolios, PnL, liquidity, and market data.
- Systems engineering: a C++ matching engine, Python orchestration, API service, database persistence, and a live frontend.
- Modern AI engineering: LLM agents, personality-driven prompts, structured outputs, tool use, retrieval-augmented generation, evidence citation, evaluation, observability, and model comparison.

The core product idea is an "AI Trading Arena": Claude and OpenAI compete through five trader personalities each, for ten total LLM-driven trading agents. They read market news, make trading decisions, submit orders into a C++ matching engine, and are ranked by profitability over time.

## Current High-Level Architecture

The project currently has these major pieces:

- `engine/`: C++17 central limit order book with price-time priority matching, market/limit orders, cancellation, snapshots, trade log, benchmark target, tests, and pybind11 bindings.
- `simulator/`: Python trading simulation layer with bot personalities, news feed, price feed, scheduler, portfolio accounting, noise traders, and reasoning logs.
- `api/`: FastAPI service exposing bots, leaderboard, order book, trades, reasoning, WebSocket events, and sandbox controls.
- `frontend/`: React/Vite/Tailwind dashboard with arena, bots, order book, and sandbox pages.
- `docker-compose.yml`: intended multi-service wrapper for API and frontend.
- `requirements.txt`: Python dependency list for simulator/backend pieces.

## What Is Completed

### C++ Trading Engine

Completed:

- Central limit order book implemented in C++.
- Buy and sell books sorted by best price.
- FIFO ordering within a price level.
- Market orders cross immediately and unfilled remainder is cancelled.
- Limit orders can rest on the book.
- Cancellation is supported through an order-id index.
- Trade log is stored and exposed.
- Top-of-book and depth snapshot support exists.
- pybind11 bindings expose the engine to Python.
- CMake structure separates engine library, executable, benchmark, Python module, and tests.

Why this matters in an interview:

- You can discuss market microstructure, price-time priority, crossing orders, liquidity, slippage, market order behavior, and trade-offs between `std::map` and lower-latency production structures.

### LLM Bot Framework

Completed:

- Five trader personalities exist:
  - `BearBot`: pessimistic, sell-biased, avoids buying.
  - `DegenBot`: aggressive momentum trader, market-order only, never holds.
  - `AnalystBot`: cautious, limit-order only, one-hour cooldown.
  - `ContrarianBot`: fades crowded moves and intraday direction.
  - `MacroBot`: trades only macro ETFs based on macro headlines.
- Each personality is instantiated for both Claude and OpenAI, giving ten LLM competitors.
- Bots request structured JSON decisions with action, ticker, quantity, limit price, reasoning, and headline used.
- Personality guardrails enforce constraints after the LLM responds.
- LLM failure falls back to `HOLD` so the simulation loop survives API failures.

Why this matters:

- This already demonstrates prompt engineering, structured output parsing, model comparison, AI-agent behavior design, and operational resilience.

### Market Data and News Inputs

Completed:

- Price data comes from `yfinance`.
- Finance/business headlines come from NewsAPI.
- News feed separates:
  - trending headlines,
  - recent headlines,
  - ticker-specific headlines.
- Feed responses are cached to reduce external API calls.
- Headlines include source, timestamp, URL, and age metadata.

Current limitation:

- This is news-driven, but not yet evidence-grounded in a true retrieval system.
- It does not yet ingest SEC filings, earnings calls, analyst notes, or macro reports.

### Simulation Orchestration

Completed:

- `BotScheduler` runs each bot on an independent timer.
- Bot starts are staggered to avoid simultaneous LLM API bursts.
- Noise traders provide basic liquidity.
- Engine access is guarded through a thread-safe adapter.
- Portfolio state updates from fills.
- Decision cycles are caught and logged so one failing bot does not crash the whole simulation.

### Persistence and Reasoning Logs

Completed:

- Bot decisions are persisted to SQLAlchemy-backed storage.
- PostgreSQL is intended for live runs.
- SQLite is used in tests/sandbox scenarios.
- Records include bot identity, action, ticker, quantity, limit price, reasoning, headline used, LLM provider, fill summary, and portfolio snapshot.
- Local JSONL fallback exists if database writes fail.

Why this matters:

- The project can show auditable AI decisions, not just black-box outputs.

### API Layer

Completed:

- FastAPI app starts the trading arena.
- Endpoints exist for:
  - health checks,
  - bot summaries,
  - bot detail,
  - leaderboard,
  - bot reasoning,
  - order book snapshots,
  - trades,
  - sandbox start/stop/status,
  - WebSocket events.
- API layer uses async wrappers around blocking portfolio, DB, and engine operations.

### Frontend Dashboard

Completed:

- React dashboard structure exists.
- Pages exist for:
  - arena overview,
  - bot details,
  - order book,
  - sandbox.
- Components exist for:
  - comparison chart,
  - leaderboard/stat bar,
  - live feed,
  - bot cards,
  - bot drawer,
  - PnL charts,
  - decision table,
  - order book panel.
- Built frontend assets exist in `frontend/dist`.

### Tests

Completed:

- Simulator tests exist for scheduler, reasoning log, price feed, portfolio, noise traders, news feed, bots, and base bot behavior.
- Engine tests exist for C++ engine behavior and Python bridge.

## What Is In Progress or Partially Complete

### End-to-End Runtime Packaging

Mostly complete after Phase 1:

- `docker-compose.yml` references API and frontend builds with explicit Dockerfiles.
- `api/Dockerfile` and `frontend/Dockerfile` now exist for local container starts.
- `requirements.txt` includes the FastAPI/Uvicorn/Pydantic/pytest runtime and test dependencies.
- `frontend/package.json` now describes the Vite/React dashboard dependencies and scripts.

Still needed:

- Add a containerized C++/pybind11 build path if Docker should run the native matching engine instead of Python stub mode.
- Add a lockfile after running `npm install` if reproducible frontend installs are desired.
- Confirm the app from a clean machine once Python, Node, CMake, API keys, and database are configured.

### Sandbox Mode

Partially complete:

- Sandbox has synthetic prices and no real news dependency.
- It runs faster for demos.
- It currently starts five Claude bots, not the full Claude-vs-OpenAI ten-bot arena.

Needed:

- Decide whether sandbox should be a lightweight demo mode or a true miniature version of the full competition.

### Fill Attribution

Mostly complete:

- C++ now exposes `getTrades()`.
- Python adapter uses `getTrades(trades_before)` to extract fills.

Watch item:

- Confirm with tests that fill attribution always maps the correct submitted order id, especially when the submitted order matches multiple resting orders.

### Documentation

Mostly complete after Phase 1:

- Code comments are fairly strong in several places.
- README now explains project purpose, architecture, setup, environment variables, run commands, tests, Docker usage, and a demo script.
- This roadmap includes chunked AI implementation prompts for the next phases.

Still needed:

- Add screenshots or a short demo recording once the dashboard is running with live data.
- Add a visual architecture diagram image if needed for slides.

## Major Missing Pieces

### RAG Evidence Layer

This is the highest-value next feature.

Goal:

- Bots should not trade only from raw headlines. They should retrieve supporting evidence from a knowledge base and cite it before placing trades.

Recommended design:

1. Ingest documents:
   - earnings call transcripts,
   - 10-K and 10-Q filings,
   - 8-Ks,
   - news articles,
   - macro reports,
   - FOMC statements,
   - CPI/jobs/GDP releases,
   - analyst-style notes generated from source documents.

2. Normalize and chunk documents:
   - source,
   - ticker,
   - company,
   - document type,
   - publish date,
   - section,
   - URL,
   - chunk text.

3. Embed chunks:
   - use OpenAI embeddings or another embedding model.
   - store vectors in a simple local vector DB first.
   - good options: Chroma, LanceDB, Qdrant, or Postgres with pgvector.

4. Retrieve evidence at decision time:
   - given bot personality, portfolio, headline, ticker, and market context, retrieve top evidence chunks.
   - optionally rerank results.

5. Require citations in the bot response:
   - `evidence_used`: list of source ids or URLs.
   - `evidence_summary`: brief explanation.
   - `confidence`: numeric score.
   - `decision`: BUY/SELL/HOLD.

6. Add a guardrail:
   - if no relevant evidence is retrieved, the bot must either HOLD or explicitly mark the trade as "headline-only/speculative."

Interview talking point:

- "I used RAG to make the agents evidence-grounded. The LLM cannot just hallucinate a thesis; it must retrieve source material and cite the documents that support the trade."

### MCP Integration

MCP means Model Context Protocol. It is a standard way for AI agents to connect to external tools, data sources, and services through a consistent protocol.

Why it fits this project:

- The trading agents need tools: market data, filings search, document retrieval, portfolio state, order submission, and risk checks.
- MCP lets you describe those capabilities as tools that an AI agent can call, instead of hardcoding every integration into one prompt flow.

Recommended MCP tools for this project:

- `get_price(ticker)`: current price and day move.
- `search_news(query, ticker, since)`: recent news.
- `search_filings(ticker, form_type, period)`: SEC filing lookup.
- `retrieve_evidence(query, ticker)`: RAG vector search.
- `get_portfolio(bot_id)`: current cash, positions, realized/unrealized PnL.
- `submit_order(bot_id, ticker, side, quantity, order_type, limit_price)`: order submission.
- `risk_check(order)`: rejects invalid or oversized trades.

Recommended demo framing:

- "The bots are not just chat prompts. They are agents with controlled tools. MCP is the interface layer between model reasoning and system actions."

### Risk Management Layer

Missing:

- Per-trade max notional.
- Per-symbol exposure limits.
- Portfolio-level drawdown limit.
- Restricted ticker universe.
- Reject orders when cash/position constraints fail.
- Kill switch for malfunctioning bots.
- Confidence threshold for trades.

Why it matters:

- Capital markets roles care deeply about controls. A strong demo should show that the agent cannot freely do reckless things just because the LLM said so.

### Evaluation and Observability

Missing:

- Prompt/version tracking.
- Decision quality metrics.
- RAG retrieval metrics.
- LLM latency and cost tracking.
- Model comparison beyond raw PnL.
- Trace view from headline -> retrieved evidence -> prompt -> model response -> risk check -> order -> fill -> PnL.

Recommended metrics:

- PnL,
- Sharpe-like return/risk ratio,
- max drawdown,
- win rate,
- turnover,
- average holding period,
- evidence citation rate,
- invalid JSON rate,
- rejected order rate,
- LLM cost per trade,
- latency per decision,
- retrieval precision spot checks.

Hot AI terms this would demonstrate:

- agent observability,
- evals,
- model benchmarking,
- structured outputs,
- tool calling,
- RAG,
- reranking,
- embeddings,
- vector search,
- guardrails,
- human-auditable reasoning.

### Backtesting and Replay

Missing:

- Historical replay of news and market data.
- Deterministic simulation runs.
- Ability to compare strategy versions against the same historical window.
- Experiment configs and result snapshots.

Why it matters:

- Live demos are impressive, but replayable experiments are more credible.

Recommended approach:

- Store news and price events as timestamped records.
- Add a replay clock.
- Let bots run against historical events.
- Save each experiment's config: model, prompt version, retrieval settings, bot settings, and risk limits.

### SEC and Earnings Data Pipeline

Missing:

- SEC EDGAR ingestion.
- Earnings transcript ingestion.
- Filing parser.
- Company/ticker mapping.
- Document freshness and source provenance.

Recommended first pass:

- Use SEC company facts/submissions APIs for filings metadata.
- Pull 10-K, 10-Q, and 8-K text for a small ticker universe: AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, SPY, QQQ.
- Add transcripts from a provider/API only if easy; otherwise seed a small local corpus for demo.

## Recommended Next Build Plan

### Phase 1: Make the Current App Presentable

Status: implemented, with full runtime verification pending local dependency setup.

- Write a real README.
- Fix dependency/package gaps.
- Confirm backend can start cleanly after Python dependencies and environment variables are installed.
- Confirm frontend can be rebuilt after `npm install`.
- Add a simple architecture diagram.
- Add a demo script.

Outcome:

- You can run the project and explain it without apologizing for setup gaps.

### Phase 2: Add RAG

Priority: very high.

- Add `rag/` or `simulator/rag/`.
- Implement document ingestion.
- Add a small seeded document corpus.
- Add embeddings and vector search.
- Modify bot prompts to require retrieved evidence.
- Persist citations in `ReasoningLog`.
- Surface citations in the frontend bot reasoning drawer.

Outcome:

- This becomes a modern AI trading-agent project, not just "LLMs read headlines."

### Phase 3: Add MCP Tool Layer

Priority: high.

- Build an MCP server that exposes market, portfolio, RAG, and order tools.
- Route at least one bot decision path through MCP tools.
- Keep order submission protected by risk checks.

Outcome:

- You can explain MCP clearly and show a real use case.

### Phase 4: Risk Controls and Evals

Priority: high.

- Add pre-trade risk checks.
- Add prompt/model version fields.
- Add latency/cost logging.
- Add evaluation dashboard metrics.
- Add invalid-response and rejected-order tracking.

Outcome:

- The system looks like something designed by someone who understands production finance constraints.

### Phase 5: Historical Replay

Priority: medium.

- Add event replay.
- Add historical news/price fixtures.
- Compare Claude vs OpenAI under the same conditions.
- Export experiment summaries.

Outcome:

- The "who is the better trader?" question becomes testable instead of anecdotal.

## What Is Currently Not Needed or Extra Weight

Avoid spending time on these until the core story is strong:

- More bot personalities. Five personalities across two model providers is enough.
- More asset classes such as options, futures, FX, or crypto.
- A full production HFT-grade engine. The current C++ engine is enough for interview purposes if you can discuss its limitations.
- Kubernetes, cloud deployment, Terraform, or complex DevOps.
- Reinforcement learning. It is tempting but would distract from the clearer LLM/RAG/MCP story.
- Complex market making logic unless you specifically want to discuss liquidity provision.
- Live scraping every source on the internet. Start with reliable APIs and a curated corpus.
- A perfect UI. The dashboard only needs to make the agent reasoning and competition legible.
- Too many indicators or technical-analysis features. The differentiator is evidence-grounded AI agents, not chart overlays.

## Suggested Interview Narrative

Short version:

"I built an AI trading arena where Claude and OpenAI compete as trading agents with five different market personalities. The agents consume market news, retrieve supporting evidence, produce structured trade decisions, pass risk controls, and submit orders into my own C++ limit order book. The system logs every decision, fill, citation, and PnL change so I can compare models and strategies over time."

Technical version:

"The C++ layer implements the market microstructure: price-time priority, order matching, market/limit behavior, cancellations, snapshots, and trades. Python orchestrates the agents, market data, news, portfolio accounting, and persistence. FastAPI exposes the live state, while React visualizes the arena. The next layer is RAG and MCP: RAG grounds each decision in filings, transcripts, macro releases, and news; MCP exposes controlled tools for retrieval, portfolio inspection, risk checks, and order submission."

## Concepts Worth Being Ready To Explain

Capital markets:

- Limit order book.
- Bid/ask spread.
- Market vs limit orders.
- Price-time priority.
- Liquidity and slippage.
- Mark-to-market PnL.
- Realized vs unrealized PnL.
- Position limits and risk checks.
- Backtesting vs live trading.
- Lookahead bias and survivorship bias.

AI/ML/Fintech:

- RAG.
- Embeddings.
- Vector databases.
- Reranking.
- Tool calling.
- MCP.
- Agentic workflows.
- Structured outputs.
- Guardrails.
- Evals.
- LLM observability/tracing.
- Model benchmarking.
- Prompt versioning.
- Hallucination control.
- Human-auditable AI decisions.

## Current Biggest Risks

- The app may not be runnable from a clean clone because package/dependency metadata is incomplete.
- The README does not yet explain the project.
- The system does not yet include RAG, MCP, risk checks, or evaluation metrics, which are the most valuable differentiators for an AI-heavy capital markets demo.
- Live data/API dependencies may make demos brittle without a reliable sandbox or replay mode.
- The dashboard exists, but the strongest story will come from showing evidence citations and decision traces, not just PnL.

## Best Next Step

The best next step is to make the current app runnable and documented, then implement RAG as the first major AI upgrade.

The highest-impact demo flow would be:

1. A headline arrives.
2. The bot retrieves related filings, transcript excerpts, and recent news.
3. The bot cites that evidence.
4. A risk check validates the proposed order.
5. The C++ engine executes or rests the order.
6. The UI shows the full chain from evidence to decision to fill to PnL.

That flow directly shows finance knowledge, C++ systems skill, and modern AI engineering in one coherent project.

## AI Implementation Chunks

This section is written for using an AI coding agent efficiently. Each chunk should be small enough to implement, test, and review without trying to rebuild the whole platform in one pass.

Recommended workflow:

- Give Codex one chunk at a time.
- Let it inspect the repo before editing.
- Ask it to implement, test, and summarize only that chunk.
- Do any required outside-VS-Code setup between chunks.
- Do not start MCP, backtesting, or advanced evals until the basic RAG path works end to end.

### Chunk 0: Stabilize the Existing App

Goal:

- Make the current repo easier to run and safer to extend.

Ask Codex:

```text
Inspect the repo and make the smallest changes needed so the backend and frontend dependency setup is clear. Update README setup instructions. Do not add RAG yet.
```

Expected changes:

- Update `README.md` with project purpose, architecture, setup, environment variables, and run commands.
- Update `requirements.txt` if FastAPI/Uvicorn/Pydantic/pytest dependencies are missing.
- Check whether `frontend/package.json` is missing; if so, either recreate it from the existing Vite app structure or document that `frontend/dist` is currently the available build artifact.
- Document how to build the C++ engine and pybind11 module.
- Document required keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NEWS_API_KEY`, `DATABASE_URL`.

Tests/checks:

- Run Python tests if dependencies are installed.
- Run C++ tests if build tools are available.
- Do not spend time fixing unrelated UI polish.

You may need to do outside VS Code:

- Create/update `.env`.
- Install Python packages.
- Install Node packages if `package.json` is restored.
- Build the C++ engine with CMake.

Stop when:

- A fresh reader can understand what the app does and how to run it.

### Chunk 1: Minimal RAG Data Model

Goal:

- Add the storage model for documents and chunks before adding live ingestion.

Ask Codex:

```text
Add a minimal RAG storage layer for financial documents and evidence chunks. Use the existing SQLAlchemy style. Start with SQLite/Postgres-compatible tables and simple keyword search fallback. Do not integrate bots yet.
```

Expected changes:

- Add a module such as `simulator/rag/`.
- Add models for:
  - `documents`,
  - `document_chunks`,
  - optionally `ingestion_runs`.
- Each document should store:
  - ticker,
  - company,
  - source,
  - document type,
  - publish date,
  - source URL,
  - raw text or cleaned text path/hash,
  - content hash,
  - created/updated timestamp.
- Each chunk should store:
  - document id,
  - ticker,
  - section,
  - chunk text,
  - chunk index,
  - source URL,
  - publish date,
  - optional embedding field placeholder.
- Add a small repository/service class for saving and querying chunks.

Recommended practical shortcut:

- Start without pgvector if it slows setup.
- Use SQL text search or simple keyword scoring first.
- Design the interface so embeddings can be added in Chunk 3.

Tests/checks:

- Unit test saving a document and chunks.
- Unit test searching chunks by ticker/query.
- Unit test deduplication by content hash.

You may need to do outside VS Code:

- Nothing unless database credentials are needed.

Stop when:

- The code can store and retrieve evidence chunks locally.

### Chunk 2: SEC Filing Ingestion MVP

Goal:

- Dynamically fetch real company filings instead of manually uploading documents.

Ask Codex:

```text
Implement the smallest SEC EDGAR ingestion MVP for 10-K, 10-Q, and 8-K documents. It should fetch filings for a small ticker list, clean text, chunk it, deduplicate it, and store chunks using the RAG storage layer.
```

Expected changes:

- Add `simulator/rag/sec_ingestion.py` or similar.
- Add a small ticker-to-CIK mapping for initial demo tickers:
  - AAPL,
  - MSFT,
  - NVDA,
  - TSLA,
  - AMZN,
  - GOOGL,
  - META.
- Fetch recent SEC submissions/filing metadata.
- Download a limited number of recent filings per ticker.
- Clean HTML/text enough for retrieval.
- Chunk documents into manageable sections.
- Store source URL and publish date.
- Track last ingestion time.

Recommended practical shortcut:

- Limit to the latest 1-3 filings per ticker at first.
- Prefer correctness and provenance over perfect parsing.

Tests/checks:

- Mock SEC HTTP responses in tests.
- Test chunking.
- Test idempotency: running ingestion twice should not duplicate chunks.

You may need to do outside VS Code:

- Confirm internet access.
- If SEC requests fail, set a proper User-Agent/contact string as recommended by SEC.

Stop when:

- Running one command can ingest SEC evidence for one or more tickers.

### Chunk 3: Embeddings and Vector Search

Goal:

- Upgrade retrieval from keyword search to semantic search.

Ask Codex:

```text
Add embeddings and vector retrieval to the RAG layer. Keep a keyword fallback so tests and local runs work without API keys.
```

Expected changes:

- Add an embedding service abstraction.
- Add OpenAI embeddings support if `OPENAI_API_KEY` is available.
- Add a deterministic fake embedding implementation for tests.
- Store embeddings in the chunk table or a related table.
- Add vector similarity search.

Vector DB choice:

- Best fit if already using Postgres: `pgvector`.
- Simpler local option: Chroma, LanceDB, or a NumPy/SQLite fallback.
- For this project, a simple local fallback is acceptable for MVP, then migrate to pgvector later.

Tests/checks:

- Test embedding generation with fake embeddings.
- Test top-k retrieval.
- Test fallback behavior when no embedding API key exists.

You may need to do outside VS Code:

- Add `OPENAI_API_KEY`.
- Install pgvector or chosen vector DB dependency if using one.
- If using Postgres pgvector, enable the extension in the database.

Stop when:

- `retrieve_evidence(ticker, query, as_of_date=None)` returns ranked evidence chunks with ids, source URLs, dates, and scores.

### Chunk 4: Bot Evidence Citations

Goal:

- Make bots cite retrieved evidence before trading.

Ask Codex:

```text
Integrate RAG retrieval into the bot decision flow. Bots should receive retrieved evidence in their prompt and return structured JSON with confidence and evidence IDs. Add a guardrail that forces HOLD or marks the trade speculative when evidence is weak.
```

Expected changes:

- Extend `OrderDecision` with:
  - confidence,
  - evidence_ids,
  - evidence_summary,
  - speculative flag.
- Update bot prompt format.
- Retrieve evidence based on ticker/headlines/context before LLM calls.
- Add guardrail:
  - if no relevant evidence above threshold, require `HOLD` or `speculative=true`.
- Persist evidence fields in `ReasoningLog`.
- Update API models to expose evidence fields.
- Update frontend decision table/drawer to show citations.

Recommended practical shortcut:

- Start with ticker-specific retrieval.
- Do not make every bot use complex multi-step planning yet.

Tests/checks:

- Test bot prompt includes evidence.
- Test LLM JSON parsing accepts new fields.
- Test missing evidence causes HOLD/speculative behavior.
- Test reasoning log persists citations.

You may need to do outside VS Code:

- Run ingestion before starting the arena.
- Verify database migration/table creation worked.

Stop when:

- A bot decision can be traced from headline to evidence chunks to trade decision.

### Chunk 5: Deterministic Risk Controls

Goal:

- Ensure LLMs cannot directly bypass trading rules.

Ask Codex:

```text
Add a deterministic risk control service and require every non-HOLD bot decision to pass risk_check_order before submitting to the engine.
```

Expected changes:

- Add `simulator/risk.py`.
- Add risk limits for:
  - max trade quantity,
  - max trade notional,
  - max position per symbol,
  - available cash,
  - no short selling unless explicitly enabled,
  - restricted ticker universe,
  - minimum confidence,
  - kill switch.
- Modify scheduler so all orders pass risk checks before `engine_adapter.submit`.
- Persist risk result and rejection reason in `ReasoningLog`.
- Expose rejected decisions in API/frontend.

Tests/checks:

- Test oversized trade rejection.
- Test insufficient cash rejection.
- Test short-selling restriction.
- Test low-confidence rejection.
- Test valid trade passes unchanged.

You may need to do outside VS Code:

- Decide exact risk limits for demo.

Stop when:

- The model can suggest a trade, but only deterministic code can approve it.

### Chunk 6: Basic Decision Trace and Metrics

Goal:

- Make the system explainable and measurable.

Ask Codex:

```text
Add a decision trace record that connects market context, retrieved evidence, model response, risk check, order, fills, and PnL. Add basic metrics for evidence citation rate, rejected orders, invalid model responses, latency, and PnL.
```

Expected changes:

- Add trace fields to decision logging or a new `decision_traces` table.
- Track:
  - prompt version,
  - model/provider,
  - retrieval query,
  - evidence ids,
  - model latency,
  - risk status,
  - order id,
  - fill count,
  - portfolio value after decision.
- Add API endpoint for trace detail.
- Add frontend view or drawer section for trace detail.

Tests/checks:

- Test traces are written for HOLD, rejected, and submitted decisions.
- Test metrics endpoint aggregates basic counts.

You may need to do outside VS Code:

- Nothing.

Stop when:

- You can show the full chain: event -> evidence -> model -> risk -> order -> PnL.

### Chunk 7: MCP Server MVP

Goal:

- Add MCP as a clean tool interface over existing backend logic.

Ask Codex:

```text
Build a minimal local MCP server for this project. It should expose tools that call existing services, not duplicate business logic. Start with read-only tools plus risk_check_order.
```

Expected MCP tools:

- `get_market_snapshot`
- `retrieve_evidence`
- `get_portfolio`
- `get_risk_limits`
- `risk_check_order`

Add later:

- `search_news`
- `search_filings`
- `get_macro_data`
- `submit_order`

Important design rule:

- MCP is the interface layer. Core logic remains in simulator/API services.

Tests/checks:

- Test each tool calls the correct service.
- Test tool responses are JSON-serializable.
- Test risk tool rejects bad orders.

You may need to do outside VS Code:

- Install MCP Python SDK or chosen local MCP package.
- Configure Claude Desktop/Codex/other client to point at the local MCP server if you want a live demo.

Stop when:

- A local MCP client can call retrieval and risk-check tools.

### Chunk 8: MCP-Guided Agent Path

Goal:

- Show that at least one bot can operate through tool calls rather than only receiving a single static prompt.

Ask Codex:

```text
Add an experimental MCP-backed decision path for one bot only, probably AnalystBot. Keep the existing direct prompt path as the default fallback.
```

Expected changes:

- Add feature flag such as `USE_MCP_AGENT_PATH`.
- Route one bot through a tool sequence:
  - get market snapshot,
  - retrieve evidence,
  - get portfolio,
  - risk check proposed order,
  - submit only if approved.
- Keep normal scheduler behavior for other bots.

Tests/checks:

- Test fallback path still works.
- Test MCP path handles tool errors by HOLDing.

You may need to do outside VS Code:

- Start the MCP server before starting the arena.

Stop when:

- You can demo "this bot is using MCP tools to reason and act."

### Chunk 9: News and Macro Ingestion

Goal:

- Expand RAG beyond SEC filings.

Ask Codex:

```text
Extend the ingestion pipeline to store recent news and macro data as RAG documents with source metadata and publish dates.
```

Expected changes:

- Store NewsAPI articles as RAG documents/chunks.
- Add FRED or similar macro ingestion if an API key/source is available.
- Tag macro documents separately.
- Make MacroBot retrieve macro evidence.

Tests/checks:

- Test news document deduplication by URL/title/hash.
- Test macro documents are retrievable by macro queries.

You may need to do outside VS Code:

- Add FRED API key if needed.
- Confirm NewsAPI key.

Stop when:

- Bot evidence can include filings, news, and macro facts.

### Chunk 10: Historical Replay MVP

Goal:

- Make comparisons reproducible.

Ask Codex:

```text
Add a minimal historical replay mode that replays stored news/evidence events and price snapshots without lookahead bias. Save each run configuration and results.
```

Expected changes:

- Add replay clock.
- Add event fixture format.
- Add `as_of_date` filtering to RAG retrieval.
- Add experiment config records:
  - model,
  - prompts,
  - bot settings,
  - risk limits,
  - retrieval settings,
  - date range.
- Add result summary:
  - PnL,
  - max drawdown,
  - trades,
  - rejected orders,
  - evidence citation rate.

Tests/checks:

- Test retrieval excludes future documents.
- Test replay is deterministic with same config.

You may need to do outside VS Code:

- Choose a small historical date range and seed documents/prices.

Stop when:

- Claude vs OpenAI can be compared on the same replay inputs.

## Suggested Codex Prompts by Phase

Use these prompts directly in future sessions.

### Prompt A: Start RAG Storage

```text
Read PROJECT_STATUS_AND_ROADMAP.md, especially "Chunk 1: Minimal RAG Data Model". Implement only that chunk. Keep changes small, add tests, and do not integrate bots yet.
```

### Prompt B: Add SEC Ingestion

```text
Read PROJECT_STATUS_AND_ROADMAP.md, especially "Chunk 2: SEC Filing Ingestion MVP". Implement only SEC ingestion for a small ticker list. Mock network calls in tests. Do not add MCP yet.
```

### Prompt C: Connect RAG to Bots

```text
Read PROJECT_STATUS_AND_ROADMAP.md, especially "Chunk 4: Bot Evidence Citations". Integrate retrieval into bot prompts and decision logging. Keep the old behavior as a fallback.
```

### Prompt D: Add Risk Controls

```text
Read PROJECT_STATUS_AND_ROADMAP.md, especially "Chunk 5: Deterministic Risk Controls". Add risk_check_order and require every non-HOLD decision to pass it before engine submission.
```

### Prompt E: Add MCP

```text
Read PROJECT_STATUS_AND_ROADMAP.md, especially "Chunk 7: MCP Server MVP". Build a local MCP server exposing retrieve_evidence, get_portfolio, get_market_snapshot, get_risk_limits, and risk_check_order. Do not move business logic into the MCP server.
```

## Practical First Implementation Target

The smallest useful RAG milestone is:

1. Store documents/chunks in the existing database.
2. Ingest one SEC filing for one ticker.
3. Retrieve evidence chunks for that ticker.
4. Add those chunks to one bot prompt.
5. Save evidence ids with the bot decision.

That is enough to honestly say:

"The trading agent uses retrieval-augmented generation. It pulls evidence from financial documents, cites the retrieved sources, and the trade is logged with its supporting evidence."
