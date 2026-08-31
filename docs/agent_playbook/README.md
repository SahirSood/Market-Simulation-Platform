# Agent Playbook

This folder is the continuation guide for future agents working on the Market
Simulation Platform.

The purpose is simple: a new agent should be able to enter the repository, read
this folder, understand what the system is, understand what has already been
built, understand what is still missing, and continue the project without asking
the same setup questions again.

This playbook is intentionally more detailed than normal documentation. It is
part roadmap, part system-design memo, part project memory, and part execution
protocol.

## Read Order For A New Agent

Read these files in order:

1. [AGENT_STATE.md](AGENT_STATE.md)
2. [01_ARCHITECTURE_AND_SYSTEM_DESIGN.md](01_ARCHITECTURE_AND_SYSTEM_DESIGN.md)
3. [02_SIX_MONTH_REPLAY_DATA_PROGRAM.md](02_SIX_MONTH_REPLAY_DATA_PROGRAM.md)
4. [03_ML_EVALUATION_AND_RESEARCH_PLAN.md](03_ML_EVALUATION_AND_RESEARCH_PLAN.md)
5. [04_ROADMAP_AND_BACKLOG.md](04_ROADMAP_AND_BACKLOG.md)
6. [05_AGENT_UPDATE_PROTOCOL.md](05_AGENT_UPDATE_PROTOCOL.md)
7. [06_INTERVIEW_SYSTEM_DESIGN_NOTES.md](06_INTERVIEW_SYSTEM_DESIGN_NOTES.md)
8. [07_REPLAY_ML_COURSE_GUIDE.md](07_REPLAY_ML_COURSE_GUIDE.md)
9. [08_FOCUSED_TRADING_ARENA_POC.md](08_FOCUSED_TRADING_ARENA_POC.md)
10. [09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md](09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md)

Use [templates/TASK_NOTE_TEMPLATE.md](templates/TASK_NOTE_TEMPLATE.md) when
recording a finished work session.

## Project One-Liner

This project is an agentic capital-markets trading simulation platform whose
first useful product is a focused AI infrastructure / large-cap technology
trading arena. LLM agents read market/news/RAG context, produce structured trade
proposals, pass through deterministic risk checks, submit approved simulated
orders into the C++ order book, and are evaluated against benchmarks through
logs, outcomes, replay, and ML analysis.

## Current North Star

The next major goal is a focused tech-sector trading arena POC, not a broad
everything-market arena and not a brief-only research app.

The first POC should answer:

```text
In this focused AI infrastructure universe, what are the bots trading, why are
they trading it, how are those trades moving through the order book and risk
layer, and are they doing better than benchmarks?
```

The immediate product rule is: keep the trading simulation real and visible,
but narrow the scope enough that the user can understand the decisions. The
main screen should lead with the live/simulated trading graph, positions,
orders, fills, PnL, and benchmark comparison. A concise recap/brief should sit
under that primary trading surface to explain the "so what":

- replay shows what the current agents would have traded historically
- RAG and historical context explain the evidence behind agent decisions
- MCP-style tools expose market, portfolio, evidence, and risk context
- deterministic risk controls govern every non-`HOLD` trade
- the C++ order book remains part of the execution story
- benchmark scoring compares bot behavior against `SPY`, `QQQ`, and later ETFs
- ML remains an evaluation layer that learns when to trust or distrust agents

The first narrow workflow is documented in
`09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md`. Use that plan to decide what
to build next before expanding the platform.

The core live agent set for this POC is:

- AnalystBot: evidence and company-specific thesis
- MacroBot: market regime, rates, and benchmark context for focused tech trades
- BearBot: downside case and counterargument

DegenBot and ContrarianBot are parked, not deleted. Keep them available for
sandbox and replay experiments, but do not center the serious first product on
them until replay/live evidence says they improve the focused arena.

The operating loop remains replay-first and live-data-confirmed:

1. Test new agent, prompt, parser, risk, replay, and ML changes against replay
   first.
2. If replay results improve or at least do not regress, let the live system keep
   collecting real decisions under market-hours and cost controls.
3. On a recurring cadence, summarize new real data, refresh outcome labels,
   update ML/evaluation reports, and decide whether the last changes helped.
4. Use replay plus fresh live data together to decide which agents to keep,
   modify, park, or reintroduce.

Replay must stay news-enriched for decision-grade ML work. Price-only replay is
allowed only as a cheap smoke test.

Important: do not silently mix replay results into live standings, and do not
present replay PnL as live investment performance.

## Source-Of-Truth Files

Core runtime:

- `api/server.py` wires the application together.
- `simulator/scheduler.py` runs live bot cycles.
- `simulator/base_bot.py` handles shared agent context, prompting, LLM parsing,
  guardrails, token/cost logging, and decision finalization.
- `simulator/bots/*.py` defines bot personalities and strategy-specific
  post-processing.
- `simulator/risk.py` implements deterministic pre-trade risk checks.
- `simulator/engine_adapter.py` is the thread-safe boundary to the C++ matching
  engine.
- `simulator/portfolio.py` tracks per-bot cash, positions, fills, and PnL.
- `simulator/reasoning_log.py` persists live decisions, execution orders,
  fills, and outcome labels.

Evaluation and replay:

- `simulator/replay.py` stores replay runs and executes historical replay events.
- `simulator/replay_workflow.py` builds isolated replay feeds, replay bots, and
  run metadata.
- `simulator/evaluation.py` summarizes decisions, compares replay runs, and
  computes replay directional scoring.
- `simulator/outcomes.py` creates future horizon labels for live decisions.
- `simulator/evaluation_scheduler.py` runs background outcome labels and
  optional scheduled replay matrices.
- `scripts/build_historical_replay_events.py` generates daily historical replay
  event files, benchmark fields, synthetic/no-lookahead context, optional local
  news-file context, and quality reports.
- `scripts/run_replay.py` runs one replay file.
- `scripts/run_replay_matrix.py` runs provider/bot replay comparisons.
- `scripts/update_decision_outcomes.py` backfills outcome labels.

RAG and tools:

- `simulator/rag/repository.py` stores documents/chunks/embeddings/job status.
- `simulator/rag/embeddings.py` contains embedding service abstractions.
- `simulator/agent_tools.py` exposes local tools for agents.
- `simulator/agent_mcp.py` adapts local tools to MCP-style JSON-RPC.
- `api/routers/mcp.py` exposes the HTTP MCP transport.

Frontend:

- `frontend/src/pages/EvalPage.jsx` is the evaluation dashboard.
- `frontend/src/pages/RetrievalPage.jsx` is the RAG/retrieval dashboard.
- `frontend/src/components/arena/*` contains the public benchmark UI.

## Non-Negotiable Operating Rules

1. Do not expose secrets in docs, logs, reports, screenshots, or generated
   artifacts.
2. Do not enable high-frequency replay automation without explicit user approval,
   because replay calls model providers and can spend tokens.
3. Do not overwrite live leaderboard data with replay data. Add a separate
   replay/backtest standings view.
4. Keep replay no-lookahead. A bot may only see data available at the simulated
   event timestamp.
5. Preserve the audit trail. Every important decision should be traceable to
   bot, provider, prompt/config, evidence, risk decision, and outcome.
6. Treat options and real shorting as later-stage features. They require stronger
   instrument models and risk controls.

## Current High-Level Status

Completed:

- Live multi-agent simulation loop.
- Claude/OpenAI provider support.
- Shared bot base class and personality-specific agents.
- Deterministic risk layer.
- C++ matching engine adapter with stub fallback.
- Portfolio accounting for long and short positions.
- RAG storage, ingestion, embeddings, retrieval, and evidence guardrails.
- MCP-style local tools and authenticated HTTP transport.
- Reasoning log, execution ledger, immediate outcomes, and horizon outcomes.
- Replay fixtures and replay matrix runner.
- Replay comparison by input fingerprint.
- Replay directional scoring.
- Evaluation dashboard columns for directional accuracy and intent PnL.
- OpenAI parser hardening.
- Historical event generation and quality reports.
- Backfilled six-month large-cap replay input using yfinance prices, official
  macro calendars, SEC EDGAR filings, and sampled GDELT GKG headline metadata.
- Full six-month no-orders replay matrix for Claude/OpenAI analyst, bear, and
  macro bots.
- First replay ML dataset export, feature dictionary, and exploratory logistic
  baseline report.
- V2 replay scoring, benchmark-relative labels, replay standings JSON,
  Markdown research report, multi-model suite, and cheap refresh automation.
- Product-facing replay research API/UI on the Evaluation page, reading the v2
  artifacts without mixing them into live standings.
- Replay decision token/cost field capture for future replay runs, plus cost
  availability snapshots in refreshed replay research artifacts.
- Replay ML course guide for understanding targets, features, labels, SPY
  benchmarks, and model interpretation.
- Focused trading arena POC doc and narrowed live-agent direction in
  `08_FOCUSED_TRADING_ARENA_POC.md`.

Major remaining work:

- Rebuild the main route so the focused trading graph/arena is first, with the
  recap/brief underneath it instead of replacing it.
- Keep `/research` as the simplified tabbed workbench for Evidence, Evaluation,
  Bots, Order Book, Behavior, and Config.
- Make benchmark-relative live/replay trading performance visible without
  mixing live standings and replay/backtest standings.
- Create large-scale replay orchestration with resume/idempotency.
- Improve HOLD/opportunity-cost labels and longer-horizon validation.
- Add matrix dry-run cost estimates before future large replay batches.
- Improve ML labels beyond the first exploratory v2 suite before trusting model
  recommendations.
- Automate a recurring evaluation loop for fresh real data.
- Add replay-regression checks after every material fix or prompt change.
- Keep Analyst/Macro/Bear live for the POC; reintroduce parked agents only
  through controlled replay/sandbox work.
- Harden 24/7 operations.
- Later: short-selling production rules and options support.

## Quick Start Commands

Run backend:

```powershell
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```

Run frontend:

```powershell
cd frontend
npm run dev
```

Run tests:

```powershell
pytest -q
```

Run frontend build:

```powershell
cd frontend
npm run build
```

Run one replay:

```powershell
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --providers claude,openai --bots analyst,bear,macro --db sqlite:///replay.db --no-orders
```

Run a matrix:

```powershell
python scripts/run_replay_matrix.py --provider-sets claude openai --bots analyst,bear,macro --db sqlite:///replay.db --no-orders --report data/replay_runs/matrix_report.json
```

Check evaluation scheduler:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/ops/evaluation/status
```

## How Future Agents Should Use This Folder

Before doing work:

1. Read this `README.md`.
2. Read `AGENT_STATE.md`.
3. Check `git status --short`.
4. Inspect any files related to the next task.
5. Confirm whether the running app is available.

While doing work:

1. Keep changes scoped.
2. Prefer existing architecture over inventing new patterns.
3. Add tests for behavior-changing work.
4. Avoid large model-provider replay runs unless the user asked for them.

After doing work:

1. Update `AGENT_STATE.md`.
2. Add a session note from `templates/TASK_NOTE_TEMPLATE.md`.
3. Mark completed backlog items in `04_ROADMAP_AND_BACKLOG.md`.
4. Record test/build results.
5. Write down the next recommended task.
