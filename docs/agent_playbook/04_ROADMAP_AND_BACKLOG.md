# Roadmap And Backlog

This document is the execution plan. Future agents should update statuses here
when tasks move from planned to in progress to completed.

Status legend:

- `[ ]` Not started
- `[~]` In progress
- `[x]` Done
- `[!]` Blocked

## Phase 0: Preserve Handoff Quality

Goal:

Make sure any future agent can understand and continue the project.

Tasks:

- [x] Create `docs/agent_playbook`.
- [x] Add architecture/system-design documentation.
- [x] Add current-state handoff file.
- [x] Add six-month replay data plan.
- [x] Add ML evaluation plan.
- [x] Add roadmap/backlog.
- [x] Add agent update protocol.
- [x] Add interview explanation notes.
- [~] Keep `AGENT_STATE.md` updated after every meaningful work session.

Acceptance criteria:

- A new agent can read the playbook and identify the next task.
- The user can use the interview notes to explain the project.

## Phase 0A: Focused Tech Trading Arena POC

Goal:

Narrow the near-term product from a broad everything-market arena into a
focused AI infrastructure / large-cap technology trading arena.

The first POC should answer:

```text
In this focused tech universe, what are the bots trading, why are they trading
it, how do orders move through risk and the C++ order book, and are the results
better than benchmarks?
```

Scope rule:

- Keep the platform as a trading simulation with real simulated BUY, SELL, HOLD,
  risk, orders, fills, order-book state, positions, and PnL.
- Narrow the first market to `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`,
  and `TSLA`; compare against `SPY` and `QQQ`.
- Use the recap/brief as a supporting explanation under the graph, not as the
  root product.
- Keep `/research` as the simplified deeper tabbed workbench.
- Existing arena, replay, RAG, MCP-style tools, risk, matching-engine, and ML
  work should remain central.

### Task 0A.0: Lock The Focused Trading Arena Direction

Status: `[x]`

Purpose:

- Correct the over-pivot into a standalone investment brief and make the active
  plan a focused trading arena with an explanatory recap.

Implemented files:

- `docs/agent_playbook/08_FOCUSED_TRADING_ARENA_POC.md`
- `docs/agent_playbook/09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md`

Acceptance criteria:

- [x] Explains that trading remains the core product.
- [x] Defines the first sector, ticker universe, benchmarks, user, and trading
  frame.
- [x] Preserves C++ order-book, RAG, MCP, risk, replay, and ML as central
  platform pieces.
- [x] Defines that the recap/brief belongs under the main graph.
- [x] Marks what should stop or wait until the focused arena works.

### Task 0A.1: Document The Core Agent Direction

Status: `[x]`

Purpose:

- Keep the live agent set small enough to understand while preserving future
  expansion paths.

Implemented file:

- `docs/agent_playbook/08_FOCUSED_TRADING_ARENA_POC.md`

Acceptance criteria:

- [x] Defines the focused trading POC user, sector, and workflow.
- [x] Defines the core live agent set.
- [x] Explains that DegenBot and ContrarianBot are parked, not deleted.
- [x] Explains how replay, RAG, MCP, risk, C++ execution, and ML support the
  narrowed trading arena.

### Task 0A.2: Park Non-Core Live Agents Without Deleting Code

Status: `[x]`

Core live agents:

- AnalystBot
- MacroBot
- BearBot

Parked agents:

- DegenBot
- ContrarianBot

Acceptance criteria:

- [x] Live API startup creates only the core agents across Claude/OpenAI.
- [x] Standalone simulator startup creates only the core agents across
  Claude/OpenAI.
- [x] Parked agent classes remain available for tests, replay, and sandbox code.
- [x] Comments explain why the parked agents are commented out.

### Task 0A.2B: Enforce Initial Tech Trading Universe Defaults

Status: `[x]`

Purpose:

- Make the runtime match the narrowed product plan instead of merely documenting
  the plan.

Implemented behavior:

- Default tradable universe is now `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`,
  `AMZN`, and `TSLA`.
- Default benchmark context is now `SPY` and `QQQ`.
- `SPY` and `QQQ` are benchmark/context symbols, not tradable by default.
- Prompt context shows the focused tradable universe and benchmark universe
  separately.
- SEC/RAG startup bootstrap defaults to the focused tech universe.
- Research ingestion no longer expands the tradable universe by default.

Acceptance criteria:

- [x] Risk checks reject symbols outside the focused tradable universe.
- [x] Agents still see benchmark context for comparison.
- [x] Config API/UI expose tradable tickers and benchmark tickers separately.
- [x] Tests cover the narrowed universe behavior.

### Task 0A.3: Add Recap/Brief Read Model

Status: `[x]`

Purpose:

- Convert existing replay/RAG/evaluation artifacts into a deterministic
  explanation layer that can sit under the main trading graph.

Implemented route:

```text
GET /evaluation/decision-brief?ticker=NVDA&sector=ai_infrastructure
```

Acceptance criteria:

- [x] Returns a deterministic, read-only recap for the initial tech universe:
  `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, and `TSLA`.
- [x] Includes trend context, benchmark comparison, agent debate, evidence,
  risk view, caveats, and what would change the view.
- [x] Compares the selected ticker against `SPY` and `QQQ`; `SMH` waits until it
  is cleanly added to the data pipeline.
- [x] Maps bot BUY/SELL/HOLD output into human-readable interpretation without
  replacing simulated trade execution.
- [x] Returns replay context and caveats without presenting replay as live
  performance.
- [x] Does not call LLM providers by default.
- [x] Does not mix live and replay metrics silently.
- [x] Uses clear fallback copy when evidence, live decisions, or replay labels
  are unavailable.

Implementation note:

- Implemented at `GET /evaluation/decision-brief`.
- The endpoint is useful, but its product position must change: it should feed
  an arena recap below the graph or remain a secondary `/brief` route, not own
  the root page.

### Task 0A.4: Build Standalone Brief Page

Status: `[x]`

Purpose:

- Preserve a readable recap surface that can be reused inside the focused arena.

Acceptance criteria:

- [x] Adds a `/brief` route.
- [x] Includes a ticker selector for the initial AI infrastructure /
  large-cap tech universe.
- [x] Includes compact sections for What Changed, Decision Options, Benchmark
  Check, Agent Debate, Evidence, Risk View, caveats, and What Would Change The
  View.
- [x] Clearly labels replay/backtest evidence.
- [x] Uses Analyst/Macro/Bear as serious perspectives.
- [x] Existing Evaluation, Research/RAG, Bots, Order Book, Behavior, and Config
  surfaces are consolidated under `/research` tabs instead of top-level nav.

Implementation note:

- `/brief` currently renders `frontend/src/pages/BriefPage.jsx`.
- Root `/` now renders `frontend/src/pages/ArenaPage.jsx`; the full recap remains
  available at `/brief` as a secondary route.
- `/research` renders `frontend/src/pages/ResearchHubPage.jsx`.
- Legacy routes redirect into `/research?tab=...`.

### Task 0A.5: Rebuild Root As Focused Trading Arena

Status: `[x]`

Purpose:

- Make the main page the focused trading simulation again, with the graph,
  orders, positions, fills, benchmarks, and risk state first.

Acceptance criteria:

- [x] Root `/` shows a selected-ticker return graph against `SPY` and `QQQ`
  before the recap.
- [x] A separate live portfolio graph compares Claude/OpenAI teams and allows
  team, all-bot, and single-bot views.
- [x] The page shows latest decisions, orders/fills, positions/PnL, and the
  public risk/execution activity trail for the focused universe.
- [x] A compact selected-ticker C++ order-book view is embedded on the page.
- [x] The existing recap appears directly underneath the market graph and uses
  the same selected ticker.
- [x] The UI labels historical replay prices, simulated execution, and live
  portfolio state separately.
- [x] `/brief` remains a secondary full recap route, not the default root.
- [x] `/research` remains the deeper tabbed workbench.

Implementation note:

- The market graph and live portfolio graph are intentionally separate so
  replay market returns are not silently mixed into live portfolio history.
- The live portfolio graph adds restrained BUY/SELL/HOLD event markers hydrated
  from persisted public-safe activity plus the WebSocket stream; team mode keeps
  individual events in a compact strip rather than implying they are team-level
  performance points.

### Task 0A.6: Make The Arena Honest And Learnable

Status: `[~]`

Purpose:

- Make the first POC credible by showing what is live, what is replay, what is
  simulated, what was risk-blocked, and what evidence is missing.

Acceptance criteria:

- The main page distinguishes live decisions, replay decisions, no-orders intent
  PnL, unavailable cost data, exploratory ML results, and missing evidence.
- HOLD states explain whether the cause is no edge, weak evidence, market-hours
  gating, budget control, or risk/reward.
- Risk rejections show deterministic reasons.
- The recap does not claim autonomous trading performance.
- The user can learn why a bot made or skipped a trade.

Current progress:

- [x] Simulation, replay-price, and live-portfolio labels are visible.
- [x] Risk, MCP/RAG, order, and execution stages are exposed through the
  public-safe activity trail.
- [x] The recap avoids claiming live autonomous investment performance.
- [x] Missing live agent views and evidence states have explicit empty states.
- [x] HOLD reasons use structured public cause labels across live decisions,
  activity events, WebSocket events, replay rows, and evaluation timelines.
- [ ] Live-versus-replay benchmark outcome reporting still needs more collected
  live decisions before it is decision-grade.

## Phase 1: Six-Month Historical Event Generation

Goal:

Generate replay-compatible, news-enriched historical event files for the past
six months.

Price-only generation is allowed only as a smoke test. The first serious
one-month pilot and the six-month dataset must include news/event context,
because the current bots trade from prices plus news/RAG evidence.

### Task 1.0: Choose Historical News/Event Context Source

Status: `[x]`

Purpose:

- Find the lowest-cost way to supply historical replay with realistic
  no-lookahead news context.

Options:

- historical news provider if affordable
- SEC/RAG filings with correct `published_at`
- market calendars such as FOMC, CPI, PCE, jobs reports, and earnings dates
- structured company events
- synthetic price-derived market summaries only as a clearly marked fallback

Acceptance criteria:

- Chosen source path is documented.
- Every headline/event has a timestamp.
- Replay can reject or flag any headline published after the replay timestamp.
- Generated events include `trending_headlines`, `recent_headlines`, and
  `ticker_headlines`.
- Synthetic summaries are marked with `synthetic: true`.

Implementation note:

- Current minimum source path is a local timestamped `--news-file` import
  adapter populated from official macro calendars, SEC EDGAR submissions,
  NewsAPI when the configured plan allows it, and sampled GDELT GKG archive
  rows. This avoids a paid-provider dependency for the first large replay.
- A paid/exhaustive historical market-news feed would still improve fidelity,
  but it is no longer blocking the first six-month no-orders replay.

### Task 1.1: Add Historical Event Builder

Status: `[x]`

Proposed file:

- `scripts/build_historical_replay_events.py`

Purpose:

- Fetch historical price/OHLCV data.
- Fetch or construct historical no-lookahead news/event context.
- Create replay-compatible event files.
- Include benchmark data.
- Include deterministic market regime features.
- Write quality report.

Suggested CLI:

```powershell
python scripts/build_historical_replay_events.py `
  --start 2026-02-18 `
  --end 2026-08-18 `
  --tickers AAPL MSFT NVDA GOOGL TSLA SPY QQQ TLT GLD IEF `
  --benchmarks SPY QQQ TLT GLD `
  --frequency 1d `
  --news-mode historical-first `
  --news-lookback-hours 24 `
  --output data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json `
  --report data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.report.json
```

Acceptance criteria:

- Generates valid replay JSON.
- Includes monotonically increasing timestamps.
- Includes `prices`, `ohlcv`, benchmark fields, and config metadata.
- Includes news/event context for decision-grade datasets.
- Supports a smoke-test mode that is clearly marked if price-only.
- Enforces no-lookahead on headline/event timestamps.
- Does not include secrets.
- Can be loaded by existing replay workflow.

Tests:

- Add tests under `simulator/tests/test_replay_datasets.py` or a new test file.
- Validate generated schema using a small fixture.

Implementation note:

- Implemented in `scripts/build_historical_replay_events.py`.
- Supports yfinance, local JSON price files, and existing replay event JSON as
  a price source for smoke tests.
- Supports `--news-mode historical-first`, `news-file`, `synthetic`, and
  `price-only`.
- Generated `price-only` files are labeled `smoke_test_price_only`; synthetic
  context is labeled and should not be treated as ML-grade historical news.

### Task 1.2: Add Generated Event Quality Report

Status: `[x]`

Report should include:

- event count
- ticker count
- benchmark count
- total headline count
- real headline count
- synthetic headline count
- events below headline minimum
- news/event sources used
- missing price count
- duplicate timestamp count
- earliest timestamp
- latest timestamp
- dropped rows
- source provider

Acceptance criteria:

- Every generated event file has a companion report.
- Report can be inspected before spending model calls.

Implementation note:

- The builder writes a companion report by default at `<output>.report.json`.
- The report includes headline counts, synthetic-vs-real counts, no-lookahead
  violation counts, missing price counts, duplicate timestamps, dropped rows,
  source provider, and dataset grade.

### Task 1.3: Create One-Month Pilot Dataset

Status: `[x]`

Goal:

- Generate roughly one month of daily events.
- Include realistic historical news/event context.
- Run a small replay matrix.
- Validate that agents produce meaningful decisions.

Acceptance criteria:

- [x] Pilot event file exists.
- [x] Pilot report exists.
- [~] Pilot has acceptable headline/news coverage.
- [x] No headlines violate no-lookahead.
- [x] Replay matrix report exists.
- [~] Costs are recorded.
- [x] Parser errors are zero or explained.

Implementation note:

- Generated on 2026-08-18:
  `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`.
- Companion report:
  `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.report.json`.
- Quality result:
  - 22 market-day events.
  - yfinance price source.
  - dataset grade: `mixed_real_and_synthetic_context`.
  - 42 real headline appearances and 206 synthetic headline appearances.
  - 6 days with any real macro context and 16 synthetic-only days.
  - 0 missing prices, 0 duplicate timestamps, 0 no-lookahead violations.
- This is acceptable for a plumbing/no-orders pilot. It is not yet
  decision-grade for ML or agent pruning because the real context is official
  macro-calendar events, not broad plus ticker-specific historical news.
- No-orders replay matrix completed on 2026-08-18:
  - Report:
    `data/replay_runs/one_month_pilot_2026-07-18_2026-08-18_report.json`
  - Claude run: `5f0ea446-0c12-4655-90ff-f2cbe4bac453`
  - OpenAI run: `c9a9b8dd-3e95-4224-be9b-ecf886c88306`
  - Decisions: 132 total.
  - Failed commands: 0.
  - Input fingerprint:
    `646572652bd0e327b89d2774ff9b7cfc4b8099449a6cd4eec71a67c5a34ac070`
- Cost was not summarized by the matrix report yet; add cost aggregation before
  relying on replay economics.

### Task 1.4: Create Full Six-Month Daily Dataset

Status: `[x]`

Acceptance criteria:

- [x] Six-month daily replay event file exists.
- [x] Covers intended date window.
- [x] Includes SPY benchmark.
- [x] Includes all configured tradable tickers with acceptable missing-data
  policy.
- [x] Includes news/event context suitable for current bot prompts.
- [x] Price-only caveat is avoided; the latest enriched output is
  `news_enriched`.

Implementation note:

- Generated on 2026-08-18:
  `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json`.
- Companion report:
  `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.report.json`.
- Macro context source:
  `data/replay_events/generated/historical_macro_context_2026-02-18_2026-08-18.json`.
- Quality result:
  - 126 market-day events.
  - yfinance price source.
  - dataset grade: `mixed_real_and_synthetic_context`.
  - 238 real headline appearances and 1,209 synthetic headline appearances.
  - 33 days with any real macro context and 93 synthetic-only days.
  - 0 missing prices, 0 duplicate timestamps, 0 no-lookahead violations.
- A dry-run matrix report exists at
  `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`.
- This original macro-plus-synthetic file should not be treated as
  decision-grade now that the backfilled large-cap file exists.
- Enriched large-cap dataset generated on 2026-08-18:
  - Context source:
    `data/replay_events/generated/historical_context_enriched_large_cap_2026-02-18_2026-08-18.json`
  - Context report:
    `data/replay_events/generated/historical_context_enriched_large_cap_2026-02-18_2026-08-18.report.json`
  - Replay file:
    `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`
  - Replay report:
    `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.report.json`
  - Tickers: 63 companies.
  - Benchmarks: 11 ETFs.
  - Events: 126 market days.
  - Dataset grade: `news_enriched`.
  - Real headline/context appearances: 2,827.
  - Synthetic headline appearances: 0.
  - Real-context days: 126.
  - Missing prices: 1 (`ABBV` on `2026-08-11T21:00:00Z`).
  - Duplicate timestamps: 0.
  - No-lookahead violations: 0.
  - Dry-run matrix:
    `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
- Backfilled large-cap dataset generated on 2026-08-18:
  - Context source:
    `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - Context report:
    `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
  - Replay file:
    `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - Replay report:
    `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
  - Tickers: 63 companies.
  - Benchmarks: 11 ETFs.
  - Events: 126 market days.
  - Dataset grade: `news_enriched`.
  - Real headline/context appearances: 5,494.
  - Synthetic headline appearances: 0.
  - Events below minimum headline coverage: 0.
  - Missing prices: 1 (`ABBV`).
  - Duplicate timestamps: 0.
  - No-lookahead violations: 0.
  - This is the preferred six-month replay input.

## Phase 2: Scalable Replay Orchestration

Goal:

Run large replay batches safely and resumably.

### Task 2.0: Run First Full Six-Month Daily Replay

Status: `[x]`

Purpose:

- Capture current bot/provider behavior over the full six-month daily backfilled
  event file.

Acceptance criteria:

- [x] Backfilled six-month event file passes quality inspection.
- [x] Claude and OpenAI provider sets run in no-orders mode.
- [x] Matrix report exists.
- [x] Decision count matches expected event/bot/provider count.

Implementation note:

- Completed on 2026-08-18:
  - Events:
    `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - Report:
    `data/replay_runs/six_month_daily_backfilled_large_cap_report.json`
  - Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`
  - OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`
  - Decisions: 756 total.
  - Failed commands: 0.
  - Input fingerprint:
    `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`
- Operational caveat: this was a direct long-running matrix execution, not a
  resumable/chunked run. Resume/chunk/progress controls are still needed before
  larger intraday or prompt-version batches.

### Task 2.1: Add Replay Resume/Skip Existing

Status: `[ ]`

Potential files:

- `scripts/run_replay_matrix.py`
- `simulator/replay.py`
- `simulator/replay_workflow.py`

Needed flags:

- `--resume`
- `--skip-existing`
- `--max-events`
- `--start-index`
- `--end-index`
- `--run-tag`

Acceptance criteria:

- Re-running the same command does not accidentally duplicate expensive runs.
- Existing matching runs are detected by fingerprint plus config.
- Reports explain what was skipped and why.

### Task 2.2: Add Replay Cost Estimate Dry Run

Status: `[ ]`

Purpose:

- Estimate number of model calls before running.
- Estimate expected spend from recent stored model cost data.

Acceptance criteria:

- `--dry-run` report includes expected events, bots, providers, calls, and cost
  estimate.
- Does not call model providers.

Implementation note:

- Actual replay decision rows now preserve token/cost fields for future replay
  runs, and the v2 research refresh reports whether those fields exist.
- This task is still open because matrix dry-runs do not yet estimate expected
  spend before model calls happen.

### Task 2.3: Add Chunked Replay Runs

Status: `[ ]`

Purpose:

- Break six-month replay into smaller date chunks.
- Make failures recoverable.

Suggested chunking:

- monthly chunks for daily replay
- weekly chunks for intraday replay

Acceptance criteria:

- Each chunk has a manifest.
- Chunks can be compared and aggregated.
- A failed chunk can be rerun independently.

## Phase 3: Replay/Backtest Standings

Goal:

Show "as if traded over six months" results without contaminating live
standings.

### Task 3.1: Add Replay Standings Aggregator

Status: `[x]`

Implemented files:

- `simulator/replay_research.py`
- `scripts/analyze_replay_research.py`

Fields:

- bot_id
- bot_name
- provider
- prompt_version
- run count
- decision count
- trade count
- hold count
- directional accuracy
- intent PnL
- approved intent PnL
- risk-blocked PnL
- benchmark return
- excess return
- cost
- citation rate
- unsupported rate
- risk rejection rate

Acceptance criteria:

- [x] Aggregates across exported replay rows.
- [x] Does not mix live rows.
- [x] Writes JSON standings and Markdown report.
- [x] Exposes the current research artifacts through a read-only API endpoint.

Implementation note:

- V2 standings artifact:
  `data/ml/reports/replay_standings_v2.json`.
- Human report artifact:
  `data/ml/reports/replay_research_report_v2.md`.
- Read-only product endpoint:
  `GET /evaluation/replay-research?version=v2`.
- Current implementation reads versioned artifacts; richer filterable
  store-backed replay standings can be added later if needed.

### Task 3.2: Add API Endpoint

Status: `[x]`

Implemented route:

```text
GET /evaluation/replay-research?version=v2
```

Current query params:

- `version`

Acceptance criteria:

- [x] Frontend can fetch replay research standings/report artifacts.
- [x] Endpoint returns no secrets.
- [x] Tests cover missing and populated artifact states.

Implementation note:

- Implemented in `api/routers/evaluation.py`.
- The endpoint returns compact model-suite target summaries, standings,
  dataset summary, manifest, Markdown report text, and cost availability.

### Task 3.3: Add Frontend Replay Standings View

Status: `[x]`

Implemented location:

- `frontend/src/pages/EvalPage.jsx`

Acceptance criteria:

- [x] User can see live outcome lab and replay research separately.
- [x] Table shows benchmark-relative results.
- [x] CSV/JSON export works.
- [x] UI shows when replay cost was not captured for the historical run.

## Phase 4: Benchmark-Relative Scoring

Goal:

Compare bots to SPY/S&P-style baseline.

### Task 4.1: Add Benchmark Price Extraction

Status: `[x]`

Need:

- extract benchmark prices from replay event payloads
- handle `SPY` first
- optionally handle `^GSPC`

Acceptance criteria:

- [x] ML export extracts `SPY` benchmark price at decision time.
- [x] ML export extracts future benchmark prices for `1d`, `3d`, and `7d`.
- [x] Missing benchmark/future data produces blank labels instead of fabricated
  values.

### Task 4.2: Add Excess Return Metrics

Status: `[x]`

Metrics:

- bot return
- benchmark return
- excess return
- excess PnL
- beat benchmark flag

Acceptance criteria:

- [x] Metrics appear in v2 ML export and standings/report artifacts.
- [x] Tests verify simple benchmark-relative price paths.
- [ ] Metrics appear in replay comparison API.
- [ ] Metrics appear in frontend.

Implementation note:

- V2 export includes `beat_benchmark_1d`, `beat_benchmark_3d`,
  `beat_benchmark_7d`, and matching excess-return columns.
- Product API/UI exposure remains open.

## Phase 5: ML Dataset Export

Goal:

Create ML-ready datasets from replay/live logs.

### Task 5.1: Add Dataset Exporter

Status: `[x]`

Proposed file:

- `scripts/export_ml_dataset.py`

Acceptance criteria:

- Exports CSV at minimum.
- Includes feature dictionary.
- Supports replay mode.
- Supports live mode later.
- Includes benchmark labels.
- Includes news context features and quality flags.
- Includes model/prompt metadata.

Implementation note:

- Replay mode v1 is implemented in `simulator/ml_dataset.py` and
  `scripts/export_ml_dataset.py`.
- The first export from the completed backfilled six-month replay is
  `data/ml/datasets/replay_decisions_v1.csv`.
- Companion summary:
  `data/ml/datasets/replay_decisions_v1.summary.json`.
- Live-decision export remains a later extension and should use the same column
  philosophy without mixing live and replay records silently.

### Task 5.2: Add Feature Dictionary

Status: `[x]`

Output:

- `data/ml/datasets/feature_dictionary_v1.md`

Acceptance criteria:

- Every column has description, type, source, and leakage risk note.

Implementation note:

- Written by the exporter at `data/ml/datasets/feature_dictionary_v1.md`.
- Label/future columns are explicitly marked as leakage risk and must not be
  used as training features.

### Task 5.3: Add Baseline Analysis Report

Status: `[x]`

Potential file:

- `scripts/analyze_replay_research.py`

Outputs:

- [x] bot/provider summary
- [x] provider summary
- [x] action summary
- [x] regime summary
- [x] confidence-bucket summary
- [x] Markdown report
- [ ] cost summary
- [ ] risk-blocked winners/losers by execution outcome

Implementation note:

- Current report:
  `data/ml/reports/replay_research_report_v2.md`.
- Cost aggregation remains a high-priority follow-up.

### Task 5.4: Add Weekly Evaluation Report Generator

Status: `[x]`

Proposed file:

- `scripts/run_weekly_evaluation_report.py`

Purpose:

- Periodically summarize fresh real data collected by the live system.
- Compare recent live outcomes with replay expectations.
- Decide whether recent fixes, prompt changes, or risk changes appear to help.

Suggested cadence:

- weekly by default
- or when at least 50 new live decisions/outcome labels exist
- monthly for deeper agent pruning review

Acceptance criteria:

- Reads stored decisions/outcomes; does not call LLM providers by default.
- Produces Markdown and JSON reports.
- Includes bot/provider/prompt-version summaries.
- Includes estimated LLM cost.
- Includes risk-blocked winners/losers when available.
- Marks reports as "monitoring only" when sample size is too small.

Completed implementation:

- `simulator/live_evaluation.py` builds JSON-safe live reports without LLM
  calls, including bot/provider/prompt-version, cost, risk-blocked, scope,
  benchmark, and replay-data caveats.
- `scripts/run_weekly_evaluation_report.py` writes Markdown and JSON artifacts.
- `EvaluationScheduler` runs the report weekly by default, and the API exposes
  `GET /evaluation/live-report` plus a compact Evaluation-page readout.
- Benchmark and same-input replay sections stay explicitly data-limited until
  live benchmark snapshots and a linked replay baseline are stored.

### Task 5.5: Add Replay Regression Report Generator

Status: `[ ]`

Proposed file:

- `scripts/run_replay_regression.py`

Purpose:

- Run a standard replay suite after prompt, parser, risk, scoring, or ML fixes.
- Compare against a prior baseline report.
- Detect behavior regressions before relying on live data.

Acceptance criteria:

- Uses a fixed fixture set by default.
- Supports provider and bot selection.
- Supports no-orders mode.
- Writes a JSON report and Markdown summary.
- Shows metric deltas versus baseline.
- Estimates or reports model call cost.

## Phase 6: Baseline ML Models

Goal:

Use ML to explain decision quality and help choose agents.

### Task 6.1: Train Logistic Regression Baseline

Status: `[x]`

Target:

- `directional_correct_next_event`

Acceptance criteria:

- Time-based split.
- Metrics report.
- Coefficients/feature importances saved.

Implementation note:

- Implemented in `simulator/baseline_model.py` and
  `scripts/train_baseline_evaluator.py`.
- First exploratory report:
  `data/ml/reports/baseline_logreg_directional_correct_v1.json`.
- The first report is pipeline-grade, not pruning-grade:
  - 211 usable directional trade rows.
  - time-split test accuracy: `0.4242`.
  - more labels, SPY-relative standing metrics, replay cost capture for new
    runs, and opportunity-cost treatment for HOLD decisions are still needed
    before pruning agents.

### Task 6.2: Train Tree-Based Baseline

Status: `[x]`

Target:

- `profitable_1d`
- or `beat_spy_1d`

Acceptance criteria:

- [x] Feature importance report.
- [x] No random split as primary result.
- [x] Leakage checks documented through feature dictionary and label-column
  guards.

Implementation note:

- Implemented in `simulator/model_suite.py` and `scripts/train_model_suite.py`.
- V2 model suite trains:
  - logistic regression
  - random forest
  - extra trees
  - gradient boosting
  - dummy-majority baseline
- Current report: `data/ml/reports/model_suite_v2.json`.

### Task 6.3: Agent Pruning Report

Status: `[ ]`

Output:

- `data/ml/reports/agent_pruning_report_v1.md`

Acceptance criteria:

- Recommends keep/modify/pause/remove for each bot/provider.
- Uses replay and live outcome evidence.
- Explains market regimes.
- Explains cost tradeoffs.

### Task 6.4: Add Data-Aware ML Refresh

Status: `[x]`

Purpose:

- Refresh ML reports when there is enough new data, not blindly every few rows.

Triggers:

- six-month replay dataset completed
- weekly live report has enough new outcome labels
- material prompt/model/risk/parser fix landed
- replay regression dataset changed materially

Acceptance criteria:

- [x] Does not call LLMs; refreshes only cheap analysis artifacts from completed
  replay rows.
- [x] Model suite warns on low usable rows and uses time-based splits.
- [x] Records dataset version.
- [x] Writes a refresh manifest.
- [ ] Writes a comparison against the previous ML report.

Implementation note:

- Implemented in `scripts/refresh_replay_research.py`.
- Current manifest: `data/ml/reports/refresh_manifest_v2.json`.

## Phase 7: Agent Optimization

Goal:

Improve the core agents and only reintroduce parked agents when evidence supports
it.

### Task 7.1: Prompt Version Registry

Status: `[ ]`

Need:

- prompt version stored on every decision
- prompt hash already exists; make it visible and queryable
- compare prompt versions in evaluation

Acceptance criteria:

- Evaluation can filter by prompt version.
- Replay run config captures prompt version.

### Task 7.2: Keep Core Agent Set To Six

Status: `[x]`

Current direction for the focused trading arena POC:

- AnalystBot x Claude/OpenAI
- MacroBot x Claude/OpenAI
- BearBot x Claude/OpenAI

ContrarianBot and DegenBot are not deleted. They are parked from serious live
startup and should remain available in replay/sandbox paths.

Acceptance criteria:

- [x] Live startup has only the core six provider-specific agents.
- [x] Parked bots are still available for replay experiments.
- [ ] Future reintroduction is justified by replay/live/ML evidence.

### Task 7.3: Add Meta-Evaluator

Status: `[ ]`

Purpose:

- Score whether to trust each proposed decision.
- Route by regime.

Acceptance criteria:

- Meta-evaluator is advisory first.
- Risk remains mandatory.
- All meta decisions are logged.

## Phase 8: Shorting And Options

Goal:

Expand supported instruments safely.

### Task 8.1: Production Shorting Rules

Status: `[ ]`

Needed:

- borrow availability
- borrow cost
- margin requirement
- short exposure caps
- forced cover logic
- locate failure handling
- separate long/short PnL reporting

Acceptance criteria:

- Short trades are explicitly modeled.
- Risk layer can reject based on borrow/margin.
- Replay can score short trades.

### Task 8.2: Instrument Abstraction

Status: `[ ]`

Need:

- stocks
- ETFs
- options
- maybe crypto later

Acceptance criteria:

- Decisions are not limited to `ticker`.
- Risk and execution understand instrument type.

### Task 8.3: Options Chain And Greeks

Status: `[ ]`

Needed:

- option symbol model
- expiration
- strike
- call/put
- bid/ask
- implied volatility
- delta/gamma/theta/vega
- max loss
- spread checks

Acceptance criteria:

- Options are paper/sim only.
- Risk can reject undefined-risk trades.
- UI can explain option exposure.

## Phase 9: 24/7 Operations

Goal:

Make the system robust enough to run continuously.

Tasks:

- [ ] Production deploy health checks.
- [ ] DB migrations verified.
- [ ] Backups.
- [ ] Log retention.
- [ ] Cost alerts.
- [ ] Scheduler status alerts.
- [ ] RAG job failure alerts.
- [ ] Replay job failure alerts.
- [ ] Weekly evaluation report automation.
- [ ] Data-threshold trigger for ML/report refresh.
- [ ] Replay-regression trigger after material fixes.
- [ ] Secrets scan in CI.
- [ ] Public read-only mode verified.
- [ ] Native engine build verified.

Important distinction:

The service can run 24/7, but live equity trading decisions should still respect
market-hours gating unless explicitly running research/replay jobs.

## Phase 10: Recruiter/Interview Polish

Goal:

Make the project easy to understand and impressive.

Tasks:

- [ ] Architecture diagram in README.
- [ ] Screenshots updated.
- [ ] "What I built" section.
- [ ] "System design decisions" section.
- [ ] "Evaluation and ML" section.
- [ ] Demo script.
- [ ] One-page technical brief.
- [ ] Replay dataset results table.
- [ ] Agent pruning report.
- [ ] Security/risk controls summary.

Best themes to emphasize:

- agentic AI
- RAG
- MCP/tool use
- deterministic guardrails
- evaluation
- replay/backtesting
- observability
- cost controls
- financial risk systems
- ML meta-evaluation
