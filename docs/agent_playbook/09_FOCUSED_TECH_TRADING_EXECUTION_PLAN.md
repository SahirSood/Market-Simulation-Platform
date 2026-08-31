# Focused Tech Trading Execution Plan

Date: 2026-08-31

This document turns the corrected product direction into an implementation
plan.

The problem is not that the platform has too much trading machinery. The
problem is that the trading machinery was spread across too many surfaces and
too broad a universe. The next phase should simplify the experience while
keeping the system a real trading simulation.

The product should be:

```text
A focused AI infrastructure trading arena where agents trade a small universe,
orders flow through deterministic risk and the C++ order book, performance is
compared to benchmarks, and a recap explains why the bots acted.
```

## Purpose Of The Change

The original project grew into a broad capital-markets platform:

- live agents
- simulated orders and fills
- C++ matching engine
- RAG evidence
- MCP-style tools
- risk controls
- replay
- outcome labels
- ML datasets
- dashboards
- many bot personalities

Those are the point of the project. Do not hide or remove them.

The correction is to narrow the market and simplify the UI:

- one coherent starting universe
- a smaller serious live-agent set
- benchmark comparison that is always visible
- one primary trading page
- one concise recap/brief below the graph
- one `/research` workbench for deeper diagnostics

## First Narrow Scope

Do not build every sector yet.

The first scope is:

- Market theme: AI infrastructure / large-cap technology.
- User: the project owner and portfolio/recruiter viewers who want to
  understand agent trading behavior.
- Primary action frame: agents submit simulated BUY, SELL, or HOLD decisions.
- Human explanation frame: add, wait, reduce, or research more can appear in
  the recap, but it must not replace trade execution.
- First tradable tickers: `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`,
  `TSLA`.
- First benchmarks: `SPY`, `QQQ`.
- Later benchmark: `SMH`, only after it is cleanly added to the price/replay
  pipeline.
- First live perspectives: Analyst, Macro, Bear across Claude and OpenAI.

Anything outside this scope must directly improve the focused trading arena or
wait.

## What We Already Have

### Product And Runtime

- FastAPI backend and React frontend.
- Live scheduler for LLM agents.
- Claude and OpenAI provider support.
- Core live agents narrowed to AnalystBot, MacroBot, and BearBot across both
  providers.
- DegenBot and ContrarianBot preserved for sandbox/replay but parked from the
  serious POC.
- Default tradable universe narrowed to `NVDA`, `AMD`, `AVGO`, `MSFT`,
  `GOOGL`, `AMZN`, and `TSLA`.
- Default benchmark context separated into `SPY` and `QQQ`.
- Research ingestion no longer expands the tradable universe by default.
- Existing arena, bot, order-book, behavior, evaluation, retrieval, and config
  pages/components.
- Deterministic recap/brief endpoint exists at `GET /evaluation/decision-brief`.
- `/research` consolidates deeper Evidence, Evaluation, Bots, Order Book,
  Behavior, and Config surfaces into tabs.
- Market-hours and cost-control concepts already exist.

### Execution, Evidence, And Guardrails

- C++ matching engine and Python adapter with stub fallback.
- RAG repository, embeddings, retrieval, and evidence identifiers.
- Local MCP-style tools for market data, portfolio state, evidence retrieval,
  risk limits, and risk preflight.
- Deterministic risk layer before simulated order execution.
- Execution ledger and reasoning log.
- Immediate and future outcome labels.

### Replay And Evaluation

- Historical replay workflow using the same agent/risk logic.
- News-enriched six-month large-cap replay input.
- Six-month no-orders replay matrix across Claude/OpenAI and Analyst/Bear/Macro.
- Replay comparison by input fingerprint.
- Replay ML export pipeline.
- V2 replay research artifacts:
  - `data/ml/datasets/replay_decisions_v2.csv`
  - `data/ml/reports/replay_standings_v2.json`
  - `data/ml/reports/replay_research_report_v2.md`
  - `data/ml/reports/model_suite_v2.json`
- Evaluation dashboard shows replay research separately from live standings.

### Current Replay Takeaway

The six-month v2 replay is useful as research evidence, but not as proof that
the bots can trade autonomously:

- 756 decisions.
- 213 trades.
- 48.34 percent one-day directional accuracy on labeled trades.
- 45.02 percent one-day beat-SPY rate on labeled trades.
- Negative one-day intent mark PnL.
- HOLD labeling is still too coarse.
- Historical replay cost was not captured for that already-completed run.

This means replay should support the arena as evaluation and caveat context. It
should not be presented as live investment performance.

## Correct Product Hierarchy

The root route should become the focused trading arena.

Recommended page order:

### 1. Trading Graph And Benchmark Context

Show the main thing first:

- portfolio value or PnL over time
- bot/provider lines or selectable series
- benchmark lines for `SPY` and `QQQ`
- focused-universe ticker selector/filter
- live vs replay/backtest label

This is the primary experience.

### 2. Market And Positions Strip

Show compact current state:

- selected ticker price and move
- benchmark moves
- cash
- position size
- exposure
- latest fill
- risk status

### 3. Latest Decisions And Orders

Show what the agents are doing:

- bot/provider
- action: BUY, SELL, HOLD
- ticker
- quantity
- limit price
- confidence
- risk result
- fill result
- short public rationale

### 4. Recap / Brief Under The Graph

Use the existing brief work here.

The recap should explain:

- what changed in the focused universe
- why the latest trades or holds happened
- what evidence was cited
- what risk controls blocked
- how the selected ticker compares with `SPY` and `QQQ`
- what would change the view

This section can use add/wait/reduce/research-more language for human
interpretation, but it should be visibly tied back to bot trade proposals.

### 5. Agent Debate And Evidence

Show Analyst, Macro, and Bear reasoning in a compact way:

- latest rationale
- cited evidence
- provider disagreement
- missing evidence warnings
- links into `/research`

### 6. Research Workbench Linkage

Keep deeper surfaces inside `/research`:

- Evidence/RAG
- Evaluation
- Bots
- Order Book
- Behavior
- Config

The old dashboards are not deleted; they are organized.

## What We Need To Build Next

### Step 1: Reposition The Existing Brief Work

Status: completed on 2026-08-31.

The existing `/brief` page and `GET /evaluation/decision-brief` endpoint were
useful and have now been repositioned under the trading-first hierarchy.

Required changes:

- root `/` should render the focused trading arena, not standalone `BriefPage`
- brief/recap content should appear underneath the main graph or as a secondary
  panel
- `/brief` can remain as a deep link for the recap, but it should not be the
  main product surface
- navigation should emphasize the main Arena/Trading page and Research

Acceptance criteria:

- A user opening `/` immediately sees trading performance, benchmarks, and
  current bot activity.
- The recap is present below the graph and explains the same selected ticker or
  universe.
- The old arena/trading functionality is still reachable.
- `/research` remains the deeper tabbed workbench.

### Step 2: Build The Focused Arena Header

Status: completed on 2026-08-31.

The first screen should make scope obvious:

- title: focused AI infrastructure trading arena
- tradable universe: `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, `TSLA`
- benchmarks: `SPY`, `QQQ`
- live/sim/replay mode label
- scheduler status
- cost/budget status

Acceptance criteria:

- The user can tell this is a trading simulation, not just an investment memo.
- The focused universe is clear.
- Benchmark context is visible without digging into config.

### Step 3: Make The Graph Actually Useful

Status: completed on 2026-08-31.

The graph should support learning from the agents.

Minimum useful graph:

- portfolio value or intent PnL over time
- benchmark comparison
- selected bot/provider filter
- markers for BUY/SELL/risk rejection/fill events
- empty states when no live decisions exist yet

Acceptance criteria:

- The graph explains both performance and behavior.
- Replay/backtest and live results are never silently mixed.
- If there is no live data yet, the graph clearly says what data is missing and
  points to replay or market-hours collection.

Current implementation:

- The first graph compares selected-ticker replay returns with `SPY` and `QQQ`.
- The second graph shows live provider/team/bot portfolio performance.
- Empty live-history states are explicit.
- Live BUY/SELL/HOLD event markers are hydrated from persisted public-safe
  activity plus the WebSocket stream and mapped to the nearest portfolio sample;
  team mode keeps the individual events in a compact strip.

### Step 4: Keep Real Trading Mechanics Visible

Status: completed for the first POC on 2026-08-31.

The main page should expose:

- current positions
- recent orders
- recent fills
- risk rejections
- cash/exposure
- C++ order-book state for selected ticker

Acceptance criteria:

- The C++ order book remains part of the demo story.
- Risk checks remain visible as the hard boundary between LLM output and
  execution.
- The page teaches why an approved trade, rejected trade, or HOLD happened.

### Step 5: Tune Core Agents For The Narrow Universe

Status: planned.

The first structured HOLD-cause pass is complete. Prompt and strategy tuning
still waits until the live arena has enough clean decisions to study.

The next model/prompt work should happen only after the focused UI is usable.

Tune:

- prompts for AI infrastructure context
- RAG queries for filings/news that matter to this universe
- MacroBot's benchmark and rate/regime framing
- BearBot's downside and valuation framing
- AnalystBot's evidence discipline

Acceptance criteria:

- Agents produce fewer generic rationales.
- Decisions cite relevant evidence when expected.
- HOLD decisions explain whether the cause is weak evidence, valuation, macro,
  risk, or no edge.

### Step 6: Improve HOLD Opportunity Labels

Status: planned.

Current replay has too many HOLD rows and coarse missed-opportunity labels.
Before using ML to judge quiet agents, improve labels so HOLD decisions can be
evaluated against:

- selected-ticker opportunity cost
- benchmark-relative opportunity cost
- focused-universe missed move
- whether the bot had enough evidence to reasonably act
- whether HOLD was correct because risk/reward was poor

### Step 7: Add Replay Cost And Resume Controls

Status: planned.

Before another expensive replay:

- add dry-run call count and cost estimate
- add skip-existing/resume behavior
- add chunked replay manifests
- keep replay automation opt-in

### Step 8: Weekly Or Threshold-Based Evaluation Report

Status: implemented; live benchmark/replay comparison remains data-limited.

Create a cheap report that reads stored decisions/outcomes and answers:

- did live data change bot standings?
- did recent prompt/risk/RAG changes improve behavior?
- did agents beat or lag benchmarks?
- which agents are too costly or too noisy?
- is there enough sample size to conclude anything?

Default cadence:

- weekly review, or
- at least 50 new decisions/outcome labels before making decision-grade claims.

The no-LLM report is available from `GET /evaluation/live-report` and
`scripts/run_weekly_evaluation_report.py`. The API scheduler writes a weekly
Markdown/JSON artifact and the Evaluation page shows its monitoring/decision-
grade status, selected-horizon outcomes, bot readout, cost, and scope caveats.

## What To Stop Doing For Now

Until the focused tech trading arena is useful, deprioritize:

- adding more sectors
- adding more primary live bot personalities
- options
- production short-selling mechanics
- broad intraday replay
- more ML model types for their own sake
- turning ML into the trader
- making a standalone investment brief the root route
- polishing every dashboard equally

The project gets stronger by making the trading loop understandable inside one
market first.

## Definition Of Done

The first POC is done when a user can open the app and understand within one
minute:

- this is a focused trading simulation
- what universe the bots are trading
- which agents are active
- what each agent bought, sold, held, or tried to trade
- what got approved or rejected by deterministic risk
- how orders/fills connect to the C++ order book
- how portfolios and PnL compare with `SPY` and `QQQ`
- what evidence/RAG context influenced decisions
- what the recap says about the current state
- whether live/replay evidence suggests the system is improving

The POC should feel like a serious capital-markets simulation lab that is
narrow enough to understand and iterate.
