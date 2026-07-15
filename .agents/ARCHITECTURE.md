# Architecture

## Purpose

This project demonstrates a full AI trading arena:

- Market structure: order books, market/limit orders, fills, slippage, portfolios, PnL.
- Systems engineering: C++ engine, Python orchestration, SQLAlchemy persistence, FastAPI, WebSockets, React.
- AI engineering: LLM bot personalities, structured decisions, RAG evidence, deterministic risk checks, and agent-tool experiments.

## Runtime Flow

```text
NewsAPI/yfinance/SEC EDGAR
  -> Python feeds and RAG repository
  -> Claude/OpenAI bot personalities
  -> BotScheduler
  -> risk_check_order()
  -> EngineAdapter
  -> C++ limit order book
  -> Portfolio + ReasoningLog
  -> Evaluation metrics + behavior analytics + replay storage
  -> FastAPI REST/WebSocket
  -> React dashboard
```

## Core Objects

- `BaseBot`: common prompt, context, RAG retrieval, LLM call, evidence guardrail.
- Bot subclasses: `BearBot`, `DegenBot`, `AnalystBot`, `ContrarianBot`, `MacroBot`.
- `BotScheduler`: runs bots/noise traders on timers and submits approved orders.
- `EngineAdapter`: thread-safe Python gateway to the native C++ order book.
- `Portfolio`: bot cash, positions, cost basis, PnL.
- `ReasoningLog`: durable decision/fill/portfolio audit trail.
- `RagRepository`: SQL-backed document/chunk/evidence store.
- `MarketAgentToolServer`: local tool registry for agent-style market/evidence/risk access.
- `ReplayStore`: Phase D storage for replay run configs, input fingerprints, and replay decisions.
- `AsOfRagRepository`: replay wrapper that prevents future RAG documents from leaking into historical decisions.
- Evaluation helpers: summarize citation quality, behavior patterns, confidence trends, fills, risk rejections, and replay metrics.

## Startup Paths

API mode:

- Entry: `api/server.py`.
- Builds feeds, engine adapter, reasoning log, RAG repository, embedding service, agent tool server, bots, noise traders, scheduler.
- Stores live objects in `api/state.py`.

Standalone simulator:

- Entry: `simulator/main.py`.
- Builds the same core simulator objects without the FastAPI layer.

Sandbox:

- Entry: `api/routers/sandbox.py`.
- Uses synthetic price/news feeds and a fast scheduler for demos.

## Decision Lifecycle

1. Bot gathers headlines, active tickers, positions, and cash.
2. Bot retrieves RAG evidence when a repository is available.
3. Bot builds a prompt and calls the configured LLM.
4. Bot normalizes or enforces personality-specific constraints.
5. RAG guardrail may force `HOLD` when evidence is weak and the trade is not marked speculative.
6. Scheduler runs deterministic `risk_check_order()` for every non-`HOLD`.
7. Approved orders go to `EngineAdapter.submit()`.
8. Fills update portfolio state.
9. `ReasoningLog` stores the decision, fills, evidence fields, and portfolio snapshot.
10. Evaluation helpers summarize citation/speculation/support metrics and per-bot behavior from logged decisions.
11. Evidence drilldown resolves cited RAG chunk ids back to filing snippets and metadata.
12. API/WebSocket/frontend surfaces update from the same state/logs.

## Replay Lifecycle

1. A replay run stores config JSON and a stable fingerprint of the input events.
2. Each timestamped event updates replay price/news inputs.
3. Replay sets an as-of clock for each event.
4. RAG retrieval receives that as-of time and filters out future documents.
5. Bot decisions are recorded to `phase_d_replay_decisions`.
6. Provider/model comparison reports group runs by identical input fingerprint.
7. Comparison metrics summarize action mix, citation/speculation/unsupported rates, risk rejections, fills, and replay portfolio snapshots.

## Persistence

Decision persistence:

- Table: `bot_decisions`.
- Code: `simulator/reasoning_log.py`.
- Fallback: `decisions_fallback.jsonl` if DB writes fail.

RAG persistence:

- Tables: `rag_documents`, `rag_chunks`.
- Code: `simulator/rag/models.py`, `simulator/rag/repository.py`.

Replay persistence:

- Tables: `phase_d_replay_runs`, `phase_d_replay_decisions`.
- Code: `simulator/replay.py`.

## Design Constraints

- Scheduler-level risk is the final order gate.
- RAG and LLM dependencies must degrade gracefully.
- Tests should mock network and LLMs.
- Bot decisions are structured JSON and should remain API-safe plain dictionaries after reads.
- Historical replay must use an as-of clock for market/news/RAG inputs.
