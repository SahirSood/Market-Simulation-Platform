# Agent State

Last updated: 2026-08-31

This file is the mutable handoff state. Future agents should update it whenever
they complete a meaningful task, discover a blocker, change project direction,
or leave work partially done.

## Current Mission

Build the project into an impressive agentic capital-markets trading simulation
for capital markets and AI-related roles.

Corrected direction as of 2026-08-31:

The immediate goal is not a standalone investment brief. That was an
overcorrection. The project should remain a trading simulation and evaluation
platform with real simulated trades, deterministic risk checks, C++ order-book
execution, RAG evidence, MCP-style tools, replay, benchmarks, and ML evaluation.

The next product goal is a focused AI infrastructure / large-cap technology
trading arena. Narrow the universe and simplify the UI, but keep the trading
loop central.

The core question is:

```text
In this focused tech universe, what are the bots trading, why are they trading
it, how do orders move through risk and the C++ order book, and are the results
better than benchmarks?
```

The existing recap/brief work is still useful, but it should sit underneath the
main graph/trading surface as an explanation layer. It should help the user
understand market data and bot decisions; it should not replace the arena.

The near-term product should emphasize three serious agent perspectives across
Claude and OpenAI:

- AnalystBot: evidence and company-specific thesis.
- MacroBot: market regime, rates, and benchmark context for focused tech trades.
- BearBot: downside case and counterargument.

DegenBot and ContrarianBot are parked, not deleted. They should stay available
for sandbox demos and controlled replay experiments, but they should not be part
of the serious first focused-arena live lineup unless evidence supports bringing
them back.

The ongoing strategic loop should be:

1. Validate changes on replay first.
2. Let the live app collect real decisions under cost and market-hours controls.
3. Refresh outcome labels automatically.
4. Run a recurring weekly or data-threshold-based evaluation report on the new
   real data.
5. Refresh ML datasets/reports after meaningful new data or material code/prompt
   changes.
6. Use the combined replay plus live evidence to decide what to fix next.

The permanent product frame is an AI trading competition. The root route must
remain the Arena/trading experience, not become a standalone brief, research
portal, or generic market dashboard. Research, RAG, MCP, replay, and ML exist
to explain the competition and make the traders better.

The expansion rule is:

```text
observe -> explain -> measure -> improve -> validate -> expand
```

Expansion means adding agents, tickers, benchmarks, or instruments only after
the current focused arena has enough clean data to show what was learned and
why the next addition is justified. Options and futures can first be added as
research context; they should become tradable only after the equity arena and
its risk/evaluation loop are understood.

Weekly is the starting cadence. If weekly live volume is too small, use a
threshold such as 50 new live decisions or 50 new outcome labels before treating
the report as decision-grade.

Important replay correction:

The first serious replay dataset must be news-enriched. The current bots make
decisions from prices plus market/news/RAG context, so price-only replay is not
representative enough for ML conclusions. Price-only generation may be used as a
smoke test for event schema and replay mechanics, but it should not be treated as
the main six-month evaluation dataset.

Important product correction:

The first user-facing POC should not be a standalone brief and should not be a
chaotic all-market leaderboard. It should lead with a focused trading graph and
arena state: portfolio/PnL, benchmarks, orders, fills, positions, risk
rejections, and latest bot decisions. The recap/brief belongs under that graph
to explain the "so what."

Immediate product surface:

- first route/workflow: focused tech-sector trading arena
- first universe: `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, `TSLA`
- first benchmarks: `SPY`, `QQQ`
- later benchmark: `SMH`, after data/replay support is added
- first bot actions: BUY, SELL, HOLD, with deterministic risk approval/rejection
- first page should show: trading graph, benchmark comparison, focused market
  strip, latest decisions, orders/fills, positions/PnL, risk rejections,
  evidence status, and an explanatory recap/brief below the graph

## Current System State

Known completed capabilities:

- Multi-agent live simulation exists.
- Agents can run with Claude and OpenAI providers.
- OpenAI parser has been hardened against empty visible content and messy JSON.
- RAG exists for evidence storage and retrieval.
- MCP-style local tools exist for market snapshot, portfolio snapshot, evidence
  retrieval, risk limits, and risk preflight.
- Deterministic risk checks exist before execution.
- Engine adapter exists as the boundary to the C++ matching engine.
- Portfolio accounting supports signed positions, including shorts at the
  portfolio layer.
- Live decisions are stored in the reasoning log.
- Execution orders and fills are stored.
- Immediate and future horizon outcome labels exist.
- Historical replay exists.
- Historical daily replay event generation exists via
  `scripts/build_historical_replay_events.py`.
- Generated replay event quality reports exist.
- Replay run comparison by `input_fingerprint` exists.
- Replay directional scoring exists.
- Evaluation dashboard displays replay comparison, outcome lab, risk rejections,
  fixture library, and export buttons.
- Replay ML dataset export exists for completed replay runs via
  `scripts/export_ml_dataset.py`.
- A feature dictionary exists at `data/ml/datasets/feature_dictionary_v1.md`.
- A lightweight baseline logistic-regression trainer exists via
  `scripts/train_baseline_evaluator.py`.
- A richer replay research refresh pipeline exists via
  `scripts/refresh_replay_research.py`; it regenerates the ML dataset, model
  suite, standings JSON, Markdown report, and manifest without calling LLMs.
- A multi-model replay suite exists via `scripts/train_model_suite.py`, covering
  logistic regression, random forest, extra trees, gradient boosting, and a
  dummy-majority baseline.
- A replay ML course guide exists at
  `docs/agent_playbook/07_REPLAY_ML_COURSE_GUIDE.md`.
- A product-facing replay research endpoint exists at
  `GET /evaluation/replay-research?version=v2`.
- The Evaluation page displays the six-month replay research summary,
  bot/provider standings, provider standings, model-suite targets, report
  export buttons, and replay cost availability separately from live standings.
- Future replay decision rows now preserve LLM token/cost fields:
  `llm_input_tokens`, `llm_output_tokens`, `llm_total_tokens`, and
  `llm_estimated_cost_usd`.
- Corrected focused trading arena POC doc exists at
  `docs/agent_playbook/08_FOCUSED_TRADING_ARENA_POC.md`.
- Focused tech trading execution plan exists at
  `docs/agent_playbook/09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md`.
- Live startup should now emphasize AnalystBot, MacroBot, and BearBot across
  Claude/OpenAI. Parked agents remain in the codebase for replay/sandbox.

Important current caveats:

- Current bundled replay fixtures are small, synthetic, and scenario-based.
- One-month and six-month generated replay input artifacts now exist under
  `data/replay_events/generated/`.
- The original one-month and first six-month artifacts use mixed macro-calendar
  plus synthetic context.
- A newer enriched six-month large-cap artifact now exists with real yfinance
  prices, 63 company tickers, 11 benchmarks, official macro-calendar context,
  SEC EDGAR filing context, and partial NewsAPI article context.
- A newer backfilled six-month large-cap artifact now exists that adds sampled
  GDELT GKG public headline/URL metadata across the full six-month window.
  This is the preferred replay input as of this handoff.
- The current historical news/event-context adapter is local-file based:
  `--news-file` plus `--news-mode historical-first`. It can now be populated by
  `scripts/build_historical_context_export.py` from macro files, SEC EDGAR,
  NewsAPI metadata when the configured NewsAPI plan allows the date range, and
  sampled GDELT GKG archive rows.
- Synthetic OHLCV-derived context is available and clearly marked, but it is
  not ML-grade historical news by itself.
- The recurring weekly live-data evaluation report now exists as a no-LLM
  scheduler/API/CLI path, but it stays monitoring-only until enough labels are
  collected.
- New immediate live outcomes now capture SPY/QQQ prices, and later horizon
  labels can calculate benchmark excess returns; older rows remain
  data-limited.
- Replay regression automation after prompt/parser/risk fixes does not exist yet.
- Replay automation is scheduler-ready but should remain opt-in because it
  spends model-provider tokens.
- The historical six-month replay completed before replay cost fields were
  stored, so exact spend for that run cannot be reconstructed. New replay runs
  will store token/cost fields when provider usage is available.
- Outcome labeling is cheap and can run automatically.
- The first replay ML model report is exploratory. It proves the dataset/model
  pipeline, but it should not drive agent pruning until benchmark standings,
  cost summaries, hold/opportunity-cost handling, and broader validation are
  added.
- The product story has been narrowed and root `/` now implements the focused
  tech trading arena with the recap directly under the benchmark graph.
- The full `/brief` route remains as a secondary detailed recap, while
  `/research` remains the deeper workbench.
- The deployed/static site can still feel broken if the backend is not running,
  if `VITE_API_URL` points at the wrong API, or if Render has not redeployed the
  latest focused-universe configuration.
- Live leaderboard and replay/backtest standings should stay separate.
- Options trading is not implemented.
- Production-quality short selling is not complete even though short positions
  and risk flags exist.
- The native C++ pybind engine is now built in the current local workspace and
  serves seeded bid/ask depth. Fresh environments may still use stub mode until
  `engine/build` is compiled.
- Long-lived PostgreSQL pools use connection pre-ping and recycling so idle
  connection expiry does not take the public API down until restart.

## Most Recent Completed Work

Focused trading arena implementation completed on 2026-08-31:

- Root `/` now renders the focused trading arena instead of the standalone
  recap.
- The first graph shows the selected tech ticker against `SPY` and `QQQ` using
  normalized six-month replay price history.
- The existing market recap now sits directly below that graph and shares the
  ticker selector.
- Live portfolio performance, latest decisions/orders/fills, positions/PnL,
  C++ book depth, RAG status, MCP/risk/execution activity, and research linkage
  remain visible on the main page.
- Navigation now emphasizes Arena, Recap, and Research.
- Stale five-strategy/ten-bot copy and fixed five-agent arithmetic were updated
  for Analyst/Macro/Bear across Claude/OpenAI.
- The arena requests a fast recap without deep evidence retrieval; the full
  `/brief` route keeps the detailed RAG evidence path.
- The portfolio graph now hydrates persisted public-safe activity and overlays
  recent BUY/SELL/HOLD markers, with a compact event strip in team mode.
- The native C++ pybind module was built locally and passed all 10 engine tests.
- The final backend regression suite passes with `232 passed`.
- Desktop and mobile browser checks confirmed the page renders without
  horizontal overflow and ticker switching updates the benchmark/recap state.
- Task 0A.5 and the structured HOLD-cause/event-marker work are complete. The
  live report is implemented; benchmark outcome reporting remains data-limited
  for historical rows until new labeled outcomes age into the report window.

Next recommended task:

- Collect a clean live decision/outcome window, let the 1d report reach its
  50-label threshold, then add persisted SPY/QQQ snapshots for honest live
  benchmark comparison.

Previous direction correction completed on 2026-08-31:

- Corrected the project direction after the brief-first plan was rejected.
- The project should remain a focused trading simulation and evaluation arena,
  not a standalone investment brief product.
- The first market remains AI infrastructure / large-cap technology:
  `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, and `TSLA`.
- Benchmarks remain `SPY` and `QQQ`, with `SMH` deferred until the data/replay
  pipeline supports it cleanly.
- The C++ order book, simulated trades, risk gate, orders, fills, positions,
  RAG evidence, MCP-style tools, replay, and ML evaluation remain central to the
  product story.
- The existing `GET /evaluation/decision-brief` endpoint and `/brief` page are
  not wasted, but should be repositioned as a recap/explanation layer underneath
  the main trading graph.
- `/research` as a tabbed workbench remains the right simplification for deeper
  Evidence, Evaluation, Bots, Order Book, Behavior, and Config surfaces.
- Replaced active planning docs:
  - `docs/agent_playbook/08_CORE_AGENT_DECISION_BRIEF.md` was replaced by
    `docs/agent_playbook/08_FOCUSED_TRADING_ARENA_POC.md`
  - `docs/agent_playbook/09_TECH_SECTOR_DECISION_BRIEF_EXECUTION_PLAN.md` was
    replaced by `docs/agent_playbook/09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md`
- Updated the roadmap Phase 0A around the focused trading arena.

Previous next recommended task:

- Task 0A.5 was to rebuild root `/` as the focused trading arena. It is now
  complete.

Superseded site/status review completed on 2026-08-31:

- Reviewed all README files plus the relevant prior planning chats.
- Confirmed the networking advice that drove the pivot: define the "so what,"
  avoid a day-trading product frame, focus one sector/use case, use historical
  trend/replay/evidence as support, and perfect the narrow POC before expanding.
- Confirmed the repo had moved materially toward that advice:
  - core live agents are AnalystBot, MacroBot, and BearBot across Claude/OpenAI
  - default local universe is `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`,
    and `TSLA`
  - benchmarks are `SPY` and `QQQ`
  - `GET /evaluation/decision-brief` exists
  - at that moment, `/` and `/brief` rendered the Investment Brief page
  - `/research` holds the deeper Evidence, Evaluation, Bots, Order Book,
    Behavior, and Config tabs
- Fixed one site/runtime wiring issue:
  - `api/server.py` now initializes `SiteAnalyticsStore`
  - `api/server.py` now mounts the existing analytics router
  - `/analytics/event` now returns `200` in local runtime smoke instead of
    `404`
- Aligned deployment config with the narrowed product:
  - `render.yaml` now sets the seven-name tech tradable universe
  - `render.yaml` now sets `BENCHMARK_TICKERS=SPY,QQQ`
  - `render.yaml` now keeps `RESEARCH_EXPAND_TRADABLE_UNIVERSE=false`
  - `render.yaml` now bootstraps RAG against the focused tech universe
- Updated deployment smoke route checks and operation docs so they validate the
  narrowed product routes rather than the old broad top-level route set. The
  later correction below clarifies that `/` should be the focused trading arena,
  with the recap/brief beneath the graph.
- Verified with:
  - `python -m py_compile api\server.py scripts\smoke_deployment.py api\tests\test_server_env.py api\tests\test_smoke_deployment.py`
  - `pytest -q api\tests\test_server_env.py api\tests\test_smoke_deployment.py api\tests\test_site_analytics.py api\tests\test_check_deploy_env.py`
    -> `28 passed`
  - `cd frontend && npm run build`
  - local offline API smoke:
    `/health`, `/ready`, `/evaluation/decision-brief`, and `/analytics/event`
    all returned `200`
  - full backend tests: `pytest -q` -> `220 passed, 1 skipped`
  - `git diff --check`

Superseded next recommended task:

- The old next task was to polish the standalone brief UI. That is no longer the
  active direction. Its replacement, Task 0A.5, rebuilt root `/` as the focused
  trading arena and is now complete.

Superseded planning update completed on 2026-08-25:

- Added `docs/agent_playbook/09_TECH_SECTOR_DECISION_BRIEF_EXECUTION_PLAN.md`.
- Clarified that the project must now answer "so what" before showing broad
  platform machinery.
- Locked the first useful POC scope to AI infrastructure / large-cap technology:
  `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, and `TSLA`.
- Confirmed first benchmarks as `SPY` and `QQQ`, with `SMH` deferred until the
  data/replay pipeline supports it cleanly.
- Clarified, at that time, that the next product work was the deterministic
  decision-brief read model plus a first-class Investment Brief frontend page.
  This was later corrected: the root product should be the focused trading
  arena, with the recap/brief underneath the graph.
- Updated the roadmap so expansion work waits until the first narrow product is
  useful.
- Enforced the initial tech trading universe in code:
  - default `TRADABLE_TICKERS`: `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`,
    `AMZN`, `TSLA`
  - default `BENCHMARK_TICKERS`: `SPY`, `QQQ`
  - prompt context now separates tradable tickers from benchmark tickers
  - default RAG bootstrap tickers now match the tech universe
  - `RESEARCH_EXPAND_TRADABLE_UNIVERSE` now defaults to `false`
  - Config API/UI now expose benchmark tickers separately
- Updated tests that still assumed `AAPL` was in the default tradable universe.
- Built the deterministic decision brief read model:
  `GET /evaluation/decision-brief?ticker=NVDA&sector=ai_infrastructure`.
- Added the new frontend brief page at `/brief` and made `/` render it.
- Simplified top-level navigation to `Brief` and `Research`.
- Added `/research` as a tabbed workbench for Evidence/RAG, Evaluation, Bots,
  Order Book, Behavior, and Config.
- Redirected legacy top-level routes such as `/eval`, `/retrieval`, `/bots`,
  `/book`, `/behavior`, and `/config` into matching `/research?tab=...` views.
- Added frontend API helper `getDecisionBrief()`.
- Verified with:
  - `python -m py_compile simulator\config.py simulator\base_bot.py simulator\model_config.py api\routers\config.py`
  - focused tests:
    `pytest -q simulator\tests\test_risk.py simulator\tests\test_llm_cost_controls.py simulator\tests\test_research.py api\tests\test_server_env.py`
    -> `41 passed`
  - replay/tool/scheduler slice:
    `pytest -q simulator\tests\test_agent_tools.py simulator\tests\test_replay.py simulator\tests\test_scheduler.py`
    -> `24 passed`
  - decision brief API focused tests:
    `pytest -q api\tests\test_evaluation_router.py::test_get_decision_brief_returns_focused_payload api\tests\test_evaluation_router.py::test_get_decision_brief_rejects_outside_universe_ticker`
    -> `2 passed`
  - frontend build: `cd frontend && npm run build`
  - full backend tests: `pytest -q` -> `219 passed, 1 skipped`

Superseded next recommended task:

- The old next task was to run the focused live loop and tune prompts for the
  brief. Its replacement, Task 0A.5, rebuilt root `/` around the focused trading
  arena and is now complete.

Most recent work completed on 2026-08-19:

- Added `GET /evaluation/replay-research?version=v2` in
  `api/routers/evaluation.py`.
- The endpoint reads versioned research artifacts from `data/ml/reports/` and
  `data/ml/datasets/`, returns compact model-suite target metrics, standings,
  dataset summary, manifest data, Markdown report text, and cost availability.
- Added API tests for populated and missing replay research artifact states.
- Added frontend API helper `getReplayResearch()` in
  `frontend/src/api/endpoints.js`.
- Added the Six-Month Replay Research panel to `frontend/src/pages/EvalPage.jsx`.
  It shows:
  - overall decision/trade counts
  - 1d directional accuracy
  - 1d beat-SPY rate
  - 1d no-orders intent PnL
  - replay cost availability
  - bot/provider standings
  - provider standings
  - model-suite target winners
  - JSON/CSV export buttons
  - expandable Markdown report text
- Added replay LLM cost/token fields to `simulator/replay.py` and migration
  `migrations/versions/0011_replay_llm_cost_tracking.py`.
- Added replay cost/token fields to the replay ML export in
  `simulator/ml_dataset.py`; the fields are classified as metrics, not model
  features.
- Added cost snapshots to replay dataset summaries and
  `simulator/replay_research.py` Markdown reports.
- Refreshed the v2 six-month research artifacts:
  `python scripts\refresh_replay_research.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --version v2 --output-dir data\ml`
- Refreshed result: 756 rows, 213 trades, 1d directional accuracy `0.4834`,
  1d beat-SPY rate `0.4502`, 1d intent PnL `-15631.548299`, and replay cost
  unavailable for the historical run because 756/756 old rows lacked stored
  cost fields.
- Verified with:
  - focused tests:
    `pytest -q simulator/tests/test_replay.py simulator/tests/test_ml_dataset.py simulator/tests/test_replay_research_models.py api/tests/test_evaluation_router.py api/tests/test_migrations.py`
    -> `27 passed`
  - frontend build: `cd frontend && npm run build`
  - full tests: `pytest -q` -> `216 passed, 1 skipped`

Most recent work completed on 2026-08-18:

- Read the full `docs/agent_playbook` folder and used it to start Phase 1.
- Added `scripts/build_historical_replay_events.py`.
- Added historical daily replay generation from yfinance or local price files.
- Added support for using existing replay event JSON as a local price source for
  builder smoke tests.
- Added local timestamped `--news-file` import support for real historical
  headlines/events when available.
- Added `historical-first`, `news-file`, `synthetic`, and `price-only` news
  modes.
- Added benchmark fields, deterministic market-regime features, generated
  per-ticker features, and explicit synthetic/no-lookahead headline metadata.
- Added generated event quality reports with dataset grade, headline coverage,
  missing price counts, duplicate timestamps, and no-lookahead violation counts.
- Added an official macro-calendar context file from Fed/BLS/BEA public release
  schedules for the 2026-02-18 through 2026-08-18 replay window.
- Generated and inspected the first one-month pilot input:
  `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`.
- Generated and inspected the six-month daily input:
  `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json`.
- Created a dry-run replay matrix report for the six-month file only; no model
  calls or replay decisions were run.
- Hardened the evaluation fixture scanner so support/source JSON files under
  `data/replay_events/generated/` are ignored instead of reported as broken
  replay fixtures.
- Ran the one-month no-orders replay matrix:
  - Claude run: `5f0ea446-0c12-4655-90ff-f2cbe4bac453`
  - OpenAI run: `c9a9b8dd-3e95-4224-be9b-ecf886c88306`
  - 132 total decisions, same input fingerprint, zero failed commands.
- Added `scripts/build_historical_context_export.py`.
- Researched practical historical news/context APIs and used the sources
  available locally:
  - SEC EDGAR for six-month ticker-specific filings.
  - NewsAPI for the locally allowed 2026-07-18 through 2026-08-18 slice.
  - official Fed/BLS/BEA macro calendars.
- Generated the enriched large-cap six-month replay input:
  `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`.
- Added sampled GDELT GKG archive backfill to
  `scripts/build_historical_context_export.py`, with strict ticker matching
  against URL-derived headline/title text to reduce noisy body-metadata matches.
- Generated the backfilled large-cap six-month context file:
  `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json`.
- Generated the preferred backfilled six-month replay input:
  `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`.
- Ran the full six-month no-orders replay matrix against the backfilled input:
  - Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`
  - OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`
  - 756 total decisions, same input fingerprint, zero failed commands.
- Added the replay ML export pipeline:
  - `simulator/ml_dataset.py`
  - `scripts/export_ml_dataset.py`
  - `simulator/baseline_model.py`
  - `scripts/train_baseline_evaluator.py`
- Exported the first six-month replay ML dataset:
  `data/ml/datasets/replay_decisions_v1.csv`.
- Wrote the first feature dictionary:
  `data/ml/datasets/feature_dictionary_v1.md`.
- Trained the first leakage-guarded, time-split baseline report:
  `data/ml/reports/baseline_logreg_directional_correct_v1.json`.
- First ML export/model summary:
  - 756 replay decision rows.
  - 213 trade rows.
  - 211 next-event directional labels.
  - overall next-event directional accuracy: `0.4834`.
  - overall SPY beat rate on scored trades: `0.4502`.
  - baseline logistic test accuracy: `0.4242`; this is exploratory and below
    the level needed for pruning decisions.
- Added v2 replay scoring, standings, model-suite, and refresh automation:
  - multi-horizon labels for `1d`, `3d`, and `7d`.
  - SPY-relative beat-benchmark labels.
  - intent mark PnL labels by horizon.
  - coarse HOLD missed-opportunity labels.
  - high-confidence-wrong and large-loss labels.
  - replay standings JSON and Markdown research report.
  - multi-model suite: logistic regression, random forest, extra trees,
    gradient boosting, and dummy-majority baseline.
  - one-command refresh via `scripts/refresh_replay_research.py`.
- Added the replay ML course guide:
  `docs/agent_playbook/07_REPLAY_ML_COURSE_GUIDE.md`.
- Updated replay file loading so API replay runs can safely use relative files
  under `data/replay_events/generated/`.
- Tightened replay event validation to reject non-increasing timestamps.
- Reconciled code with already-documented completed behavior:
  - OpenAI empty visible content retry and robust JSON parsing.
  - Immediate decision outcome persistence in `ReasoningLog`.
  - Evaluation scheduler config defaults.
  - MacroBot recognition for broader macro terms such as jobless claims, PMI,
    credit spreads, and liquidity.
- Added focused tests for generated replay event building and no-lookahead
  headline filtering.
- Verified with:
  - `pytest -q` -> `213 passed, 1 skipped`

Previous work completed before this file was created:

- Fixed OpenAI response parsing in `simulator/base_bot.py`.
- Added robust JSON parsing for fenced or surrounding text responses.
- Added one retry path for empty OpenAI visible content using low reasoning
  effort.
- Ran manual replay matrices for:
  - `sample_earnings_miss`
  - `sample_fed_rate_shock`
  - `sample_market_selloff`
- Added replay directional scoring in `simulator/evaluation.py`.
- Added frontend columns for directional accuracy and intent PnL.
- Fixed replay matrix report success counting.
- Verified with backend tests and frontend build at that time:
  - `206 passed, 1 skipped`
  - `npm run build` succeeded

Manual replay data from that run:

- 6 replay runs.
- 54 replay decisions.
- Provider sets: Claude and OpenAI separately.
- Bots: analyst, bear, macro.
- Execution mode: `--no-orders`.
- Report artifact: `data/replay_runs/manual_three_fixture_matrix_report.json`.

## Current Data Inventory

Live/evaluation:

- Existing live decisions were present in the database at last check.
- A prior outcome-labeling run created/skipped labels across horizons:
  - `1h`
  - `6h`
  - `1d`
  - `7d`
- The 1,436 label number came from:

```text
359 decisions x 4 horizons = 1,436 outcome labels
```

Replay:

- Bundled replay fixtures live in `data/replay_events`.
- Current fixture files:
  - `sample_ai_infrastructure_cycle.json`
  - `sample_earnings_beat.json`
  - `sample_earnings_miss.json`
  - `sample_fed_rate_shock.json`
  - `sample_liquidity_rotation.json`
  - `sample_market_selloff.json`
  - `sample_sec_filing_risk.json`
- Generated replay input artifacts live in `data/replay_events/generated`.
- Macro context source:
  - `historical_macro_context_2026-02-18_2026-08-18.json`
  - 35 official timestamped macro-calendar events from Federal Reserve, BLS,
    and BEA public release schedules.
- One-month pilot input:
  - `one_month_pilot_2026-07-18_2026-08-18.json`
  - report: `one_month_pilot_2026-07-18_2026-08-18.report.json`
  - source provider: yfinance
  - events: 22 market days
  - dataset grade: `mixed_real_and_synthetic_context`
  - headline appearances: 42 real, 206 synthetic
  - days with any real context: 6
  - synthetic-only days: 16
  - missing price count: 0
  - duplicate timestamp count: 0
  - no-lookahead violations: 0
- Six-month daily input:
  - `six_month_daily_2026-02-18_2026-08-18.json`
  - report: `six_month_daily_2026-02-18_2026-08-18.report.json`
  - source provider: yfinance
  - events: 126 market days
  - dataset grade: `mixed_real_and_synthetic_context`
  - headline appearances: 238 real, 1,209 synthetic
  - days with any real context: 33
  - synthetic-only days: 93
  - missing price count: 0
  - duplicate timestamp count: 0
  - no-lookahead violations: 0
- Enriched large-cap context source:
  - `historical_context_enriched_large_cap_2026-02-18_2026-08-18.json`
  - report: `historical_context_enriched_large_cap_2026-02-18_2026-08-18.report.json`
  - tickers: 63 companies
  - context rows: 711
  - replay source counts: 560 SEC EDGAR filings, 116 NewsAPI article rows,
    35 official macro-calendar rows
  - NewsAPI caveat: current key hit the developer-plan archive/rate limits; it
    contributed only the allowed 2026-07-18 through 2026-08-18 slice.
- Enriched six-month daily input:
  - `six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`
  - report: `six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.report.json`
  - source provider: yfinance
  - events: 126 market days
  - tradable tickers: 63 companies
  - benchmarks: 11 ETFs (`SPY`, `QQQ`, `TLT`, `GLD`, `IEF`, `IWM`, `XLF`,
    `XLK`, `XLE`, `XLV`, `XLY`)
  - dataset grade: `news_enriched`
  - headline/context appearances: 2,827 real, 0 synthetic
  - real-context days: 126
  - synthetic-only days: 0
  - unique real titles surfaced in replay events: 683
  - missing price count: 1 (`ABBV` missing on `2026-08-11T21:00:00Z`)
  - duplicate timestamp count: 0
  - no-lookahead violations: 0
- Backfilled large-cap context source:
  - `historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - report: `historical_context_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
  - tickers: 63 companies
  - context rows: 1,861
  - replay source counts: 1,266 GDELT GKG sampled public article rows,
    560 SEC EDGAR filing rows, and 35 official macro-calendar rows
  - NewsAPI caveat: the configured developer-plan key was rate-limited during
    this run, so it contributed 0 fresh rows to the backfilled context.
  - GDELT caveat: this is a sampled archive backfill using three UTC archive
    slices per day (`13:00`, `16:00`, `20:00`), URL-derived titles, and up to
    300 fetched page titles. It is real public metadata, not an exhaustive paid
    historical market-news feed.
- Backfilled six-month daily input:
  - `six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - report: `six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
  - source provider: yfinance
  - events: 126 market days
  - tradable tickers: 63 companies
  - benchmarks: 11 ETFs (`SPY`, `QQQ`, `TLT`, `GLD`, `IEF`, `IWM`, `XLF`,
    `XLK`, `XLE`, `XLV`, `XLY`)
  - dataset grade: `news_enriched`
  - headline/context appearances: 5,494 real, 0 synthetic
  - events below minimum headline coverage: 0
  - missing price count: 1 (`ABBV`)
  - duplicate timestamp count: 0
  - no-lookahead violations: 0
- One-month pilot replay run:
  - report: `data/replay_runs/one_month_pilot_2026-07-18_2026-08-18_report.json`
  - command count: 2
  - succeeded: 2
  - failed: 0
  - decisions: 66 Claude + 66 OpenAI = 132
  - input fingerprint:
    `646572652bd0e327b89d2774ff9b7cfc4b8099449a6cd4eec71a67c5a34ac070`
- Dry-run replay matrix report:
  - `six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
  - planned no-order replay commands for Claude and OpenAI across analyst,
    bear, and macro bots.
  - dry run only; no provider calls, decisions, or costs.
- Enriched six-month dry-run replay matrix report:
  - `six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
  - planned no-order replay commands for Claude and OpenAI across analyst,
    bear, and macro bots.
  - dry run only; no provider calls, decisions, or costs.
- Backfilled six-month replay run:
  - report: `data/replay_runs/six_month_daily_backfilled_large_cap_report.json`
  - command count: 2
  - succeeded: 2
  - failed: 0
  - decisions: 378 Claude + 378 OpenAI = 756
  - Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`
  - OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`
  - input fingerprint:
    `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`
  - operational warnings: local engine adapter ran in stub mode, one Claude
    BearBot response needed failure handling, and two OpenAI BearBot calls hit
    model output limits. The replay commands still completed and recorded all
    expected decisions.
- ML artifacts from the backfilled six-month replay:
  - dataset: `data/ml/datasets/replay_decisions_v1.csv`
  - summary: `data/ml/datasets/replay_decisions_v1.summary.json`
  - feature dictionary: `data/ml/datasets/feature_dictionary_v1.md`
  - baseline report:
    `data/ml/reports/baseline_logreg_directional_correct_v1.json`
  - exported rows: 756 replay decisions
  - trade rows: 213
  - labeled next-event trade rows: 211
  - aggregate directional accuracy: `0.4834`
  - aggregate beat-SPY rate: `0.4502`
  - by scored trade group:
    - Claude BearBot: 121 trades, `0.4959` directional accuracy, `-6786.05`
      intent mark PnL.
    - OpenAI BearBot: 88 trades, `0.4545` directional accuracy, `-9223.50`
      intent mark PnL.
    - Claude MacroBot: 2 trades, `1.0` directional accuracy, `378.00`
      intent mark PnL; sample too small to interpret.
  - AnalystBot mostly held, so it has little directional label signal in this
    first export.
- V2 replay research artifacts:
  - dataset: `data/ml/datasets/replay_decisions_v2.csv`
  - summary: `data/ml/datasets/replay_decisions_v2.summary.json`
  - feature dictionary: `data/ml/datasets/feature_dictionary_v2.md`
  - model suite: `data/ml/reports/model_suite_v2.json`
  - standings: `data/ml/reports/replay_standings_v2.json`
  - Markdown report: `data/ml/reports/replay_research_report_v2.md`
  - refresh manifest: `data/ml/reports/refresh_manifest_v2.json`
  - latest refresh timestamp: `2026-08-19T02:15:11Z`
  - exported rows: 756 replay decisions
  - trade rows: 213
  - HOLD rows: 543
  - 1d directional accuracy: `0.4834`
  - 1d beat-SPY rate: `0.4502`
  - 1d intent mark PnL: `-15631.548299`
  - 3d directional accuracy: `0.4444`
  - 3d beat-SPY rate: `0.4396`
  - 3d intent mark PnL: `-22530.248187`
  - 7d directional accuracy: `0.4428`
  - 7d beat-SPY rate: `0.4179`
  - 7d intent mark PnL: `-54197.800866`
  - best v2 test-accuracy model for `directional_correct_1d`: `extra_trees`
    with test accuracy `0.6061`
  - best v2 test-accuracy model for `beat_benchmark_1d`: `extra_trees` with
    test accuracy `0.6970`
  - replay cost snapshot: unavailable for this historical run; `0` recorded
    cost rows and `756` missing cost rows because these replay decisions were
    recorded before replay cost fields existed.
  - caveat: test splits are small, so these are research signals, not production
    trading rules.

## Immediate Next Task

Improve the next data cycle now that completed v2 replay research artifacts are
visible through API/UI.

Recommended next implementation:

1. Improve HOLD opportunity-cost labels so quiet bots can be judged more fairly.
2. Add replay resume/chunk/progress controls before any larger intraday or
   prompt-version replay batch.
3. Add matrix dry-run cost estimates now that future replay rows can capture
   actual token/cost fields.
4. Then run a richer agent-pruning report. Do not prune solely from the v2
   model suite; the test splits are still small.

The completed six-month run used:

```text
126 events x 3 bots x 2 providers = 756 model calls
```

## Six-Month Replay Window

As of this file's creation date, 2026-08-18, the requested six-month lookback is:

```text
2026-02-18 through 2026-08-18
```

Future agents should recompute the six-month window from the current date if the
user asks for "past six months" again.

## Core Six-Agent Set For The Focused Trading Arena POC

Current user direction: reduce the serious live lineup from 10 agents to 6 for
the first POC, without deleting the parked agents.

Core live/replay set:

- AnalystBot with Claude
- AnalystBot with OpenAI
- BearBot with Claude
- BearBot with OpenAI
- MacroBot with Claude
- MacroBot with OpenAI

Reason:

- AnalystBot tests evidence-grounded fundamental/trend reasoning.
- BearBot tests downside/risk sensitivity.
- MacroBot tests broad market and rates logic.
- Claude/OpenAI comparison remains fair because both see the same replay inputs.

ContrarianBot and DegenBot should not be deleted. They are parked for now and
should be reintroduced only in controlled sandbox/replay batches once the
focused trading arena POC is useful.

## Cost And Safety Notes

The expensive unit is a model decision call.

Approximate call count formula:

```text
events x bots x providers x prompt_versions
```

Example:

```text
126 trading days x 3 bot personalities x 2 providers x 1 prompt version
= about 756 model calls
```

If bot identities already include provider, then count as:

```text
126 trading days x 6 provider-specific bots = about 756 model calls
```

Intraday replay multiplies this quickly:

```text
126 trading days x 4 events per day x 6 provider-specific bots
= about 3,024 model calls
```

Therefore, do this in stages:

1. One-month daily pilot.
2. Six-month daily replay.
3. Selected high-volatility intraday replay.
4. Only then consider broad intraday replay.

Do not enable scheduled replay at high frequency without explicit user approval.

## Open Design Questions

These are not blockers for the next step, but they should be decided soon:

- Should the sampled GDELT/SEC/macro backfill be upgraded later with a paid
  exhaustive historical market-news feed?
- What minimum headline coverage makes a replay dataset decision-grade?
- Should generated replay events be daily JSON files, one large JSON file, or
  JSONL shards?
- Should replay standings include only approved trades, or also "intent PnL" for
  risk-blocked ideas?
- Should the initial benchmark be `SPY`, `^GSPC`, or both?
- Should prompt changes be treated as separate "strategy versions" in the UI?

## Current Backlog Snapshot

High priority:

- [~] Focused trading arena POC for AI infrastructure / large-cap tech.
- [x] Core-agent POC direction documented.
- [x] Live startup narrowed to AnalystBot, MacroBot, and BearBot while preserving
  parked agent code.
- [x] Historical news/event-context adapter for replay.
- [x] Historical replay event generator.
- [x] Generated replay event validation.
- [x] One-month replay pilot input generated and no-orders replay completed.
- [x] Six-month enriched large-cap input generated and inspected.
- [x] Six-month backfilled large-cap no-orders replay completed.
- [ ] Six-month replay run plan with chunking and resume.
- [x] Benchmark-relative scoring.
- [x] Replay/backtest research endpoint and Eval page panel.
- [x] ML dataset exporter.
- [x] First replay feature dictionary and baseline logistic report.

Medium priority:

- [ ] Prompt version tracking improvements.
- [ ] Model/prompt experiment registry.
- [ ] Regime classification.
- [ ] Agent pruning report.
- [ ] Replay scheduling presets.
- [~] Cost dashboard for replay batches.
- [ ] Weekly/data-threshold evaluation automation.
- [ ] Replay-regression suite after material fixes.
- [ ] ML report refresh after prompt/risk/parser changes.
- [x] Recap/brief API/read model from existing replay/RAG/evaluation data.
- [x] Standalone `/brief` frontend page, to be repositioned under the arena.
- [x] Rebuild root `/` as the focused trading arena with recap below graph.

Later:

- [ ] Reintroduce ContrarianBot and DegenBot only after controlled replay evidence
  or as explicitly labeled sandbox agents.
- [ ] Production shorting rules.
- [ ] Options instrument model.
- [ ] Options chain ingestion.
- [ ] Greeks/risk checks.
- [ ] 24/7 deployment hardening.
- [ ] External monitoring/alerts.

## Update Log

### 2026-08-31

Summary:

- Corrected the active product direction from brief-first to focused trading
  arena first.
- Preserved the narrowed universe, benchmark split, core six-agent live set, and
  `/research` tabbed workbench simplification.
- Clarified that the existing recap/brief endpoint and page should be reused
  under the main trading graph, not treated as the root product.
- Replaced the active pivot docs with focused trading arena docs.

Files changed:

- `README.md`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/08_FOCUSED_TRADING_ARENA_POC.md`
- `docs/agent_playbook/09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md`
- `docs/agent_playbook/session_notes/2026-08-31_focused_trading_arena_correction.md`

Next recommended task:

- Completed by the focused arena implementation follow-up below.

### 2026-08-31 (implementation follow-up)

Summary:

- Rebuilt root `/` as the focused trading arena with the recap directly below
  the selected-ticker benchmark graph.
- Added structured HOLD causes across live decisions, persistence, replay,
  evaluation, activity, WebSocket events, and the UI.
- Added persisted and live BUY/SELL/HOLD markers to the portfolio graph.
- Aligned MacroBot and the deterministic risk boundary with the focused tech
  universe, keeping `SPY` and `QQQ` benchmark-only.
- Hardened long-lived PostgreSQL pools against idle connection expiry.

Verification:

- `pytest -q` -> `232 passed`
- Native C++ tests -> `10/10 passed`
- Frontend production build passed.
- Desktop and mobile browser checks passed without horizontal overflow.

Next recommended task:

- Collect a clean live decision/outcome window, let the 1d report reach its
  50-label threshold, then add persisted SPY/QQQ snapshots for honest live
  benchmark comparison.

### 2026-08-31 (live evaluation report)

Summary:

- Added `simulator/live_evaluation.py`, a no-LLM report builder that keeps live
  decisions/outcomes separate from replay and marks thin samples as monitoring
  only.
- Added bot/provider/prompt-version summaries, estimated cost, risk-blocked
  order review, focused-universe coverage, and explicit benchmark/replay data
  caveats.
- Added `scripts/run_weekly_evaluation_report.py`, API endpoint
  `GET /evaluation/live-report`, Evaluation-page readout, and weekly scheduler
  wiring in both API and standalone simulator startup.
- Added SPY/QQQ price capture at immediate outcome time and benchmark excess-
  return calculations when horizon labels have both price observations.

Verification:

- Focused report/API/scheduler suite passed: `27 passed`.
- Full backend, native C++, and frontend checks passed for this update.

Next recommended task:

- Collect enough fresh `1d` outcome labels to cross the 50-label threshold,
  then persist SPY/QQQ observation snapshots before claiming live benchmark
  outperformance.

### 2026-08-20

Summary:

- Pivoted the project direction toward a focused investment decision brief POC
  for AI infrastructure / large-cap technology.
- Documented the core POC agent set: AnalystBot, MacroBot, and BearBot across
  Claude/OpenAI.
- Parked DegenBot and ContrarianBot from the serious live lineup without
  deleting their code.
- Preserved replay/ML/RAG/risk/matching-engine work as the evidence and
  evaluation backbone for the brief.

Files changed:

- `api/server.py`
- `simulator/main.py`
- `README.md`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/06_INTERVIEW_SYSTEM_DESIGN_NOTES.md`
- `docs/agent_playbook/08_CORE_AGENT_DECISION_BRIEF.md`
- `docs/agent_playbook/session_notes/2026-08-20_core_agent_decision_brief_pivot.md`

Commands run:

- `python -m py_compile api\server.py simulator\main.py`
- `pytest -q simulator/tests/test_bots.py simulator/tests/test_replay_datasets.py api/tests/test_server_env.py`
- `pytest -q simulator/tests/test_replay.py simulator/tests/test_replay_datasets.py api/tests/test_smoke_deployment.py`

Results:

- Python compile passed for the changed startup files.
- Focused bot/replay/server-env tests passed: `14 passed`.
- Replay/server smoke slice passed: `13 passed`.

Superseded next recommended task:

- The old next task was to build the decision-brief API/read model and focused
  Investment Brief frontend page. That work exists now, but the active product
  correction is to reuse it under the focused trading arena rather than making
  it the root product.

Open questions:

- Should the first sector universe be exactly `NVDA`, `AMD`, `AVGO`, `MSFT`,
  `GOOGL`, `AMZN`, and `TSLA`, or should it include more semiconductor/AI
  infrastructure names?
- Should the brief's primary benchmark be `QQQ` until `SMH` is added?

### 2026-08-19

Summary:

- Added product-facing replay research API/UI for the v2 six-month artifacts.
- Added replay decision token/cost fields for future replay runs.
- Added replay cost snapshots to ML dataset summaries and Markdown reports.
- Refreshed v2 six-month replay research artifacts with explicit cost
  availability.

Files changed:

- `api/routers/evaluation.py`
- `api/tests/test_evaluation_router.py`
- `api/tests/test_migrations.py`
- `frontend/src/api/endpoints.js`
- `frontend/src/pages/EvalPage.jsx`
- `simulator/replay.py`
- `simulator/ml_dataset.py`
- `simulator/replay_research.py`
- `simulator/baseline_model.py`
- `simulator/tests/test_replay.py`
- `simulator/tests/test_ml_dataset.py`
- `migrations/versions/0011_replay_llm_cost_tracking.py`
- `data/ml/datasets/replay_decisions_v2.csv`
- `data/ml/datasets/replay_decisions_v2.summary.json`
- `data/ml/datasets/feature_dictionary_v2.md`
- `data/ml/reports/model_suite_v2.json`
- `data/ml/reports/replay_standings_v2.json`
- `data/ml/reports/replay_research_report_v2.md`
- `data/ml/reports/refresh_manifest_v2.json`

Commands run:

- `pytest -q simulator/tests/test_replay.py simulator/tests/test_ml_dataset.py simulator/tests/test_replay_research_models.py api/tests/test_evaluation_router.py api/tests/test_migrations.py`
- `python scripts\refresh_replay_research.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --version v2 --output-dir data\ml`
- `cd frontend && npm run build`
- `pytest -q`

Results:

- Focused tests: `27 passed`.
- Frontend production build succeeded.
- Full test suite: `216 passed, 1 skipped`.
- Refreshed v2 report still shows weak current trading performance:
  `48.34%` 1d directional accuracy, `45.02%` 1d beat-SPY rate, and
  `-15,631.55` 1d no-orders intent PnL.
- Cost result: historical v2 replay cost is unavailable because all 756 old
  replay rows were recorded before replay token/cost fields existed. Future
  replay rows will preserve those fields.

### 2026-08-18

Summary:

- Added a replay ML dataset exporter and feature dictionary writer.
- Added a lightweight, dependency-free logistic-regression baseline trainer.
- Exported the completed backfilled six-month replay into an ML-ready CSV.
- Trained the first exploratory directional-correct baseline model.
- Updated handoff docs so future agents start from standings/analysis instead
  of re-running the replay or export.

Files changed:

- `simulator/ml_dataset.py`
- `simulator/baseline_model.py`
- `scripts/export_ml_dataset.py`
- `scripts/train_baseline_evaluator.py`
- `simulator/tests/test_ml_dataset.py`
- `simulator/tests/test_baseline_model.py`
- `data/ml/datasets/replay_decisions_v1.csv`
- `data/ml/datasets/replay_decisions_v1.summary.json`
- `data/ml/datasets/feature_dictionary_v1.md`
- `data/ml/reports/baseline_logreg_directional_correct_v1.json`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/session_notes/2026-08-18_six_month_replay_ml_export.md`

Commands run:

- `python -m py_compile simulator\ml_dataset.py simulator\baseline_model.py scripts\export_ml_dataset.py scripts\train_baseline_evaluator.py`
- `pytest -q simulator\tests\test_ml_dataset.py simulator\tests\test_baseline_model.py`
- `python scripts\export_ml_dataset.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --output data\ml\datasets\replay_decisions_v1.csv --dictionary data\ml\datasets\feature_dictionary_v1.md --summary data\ml\datasets\replay_decisions_v1.summary.json`
- `python scripts\train_baseline_evaluator.py --dataset data\ml\datasets\replay_decisions_v1.csv --target directional_correct_next_event --report data\ml\reports\baseline_logreg_directional_correct_v1.json --epochs 500 --min-rows 50`
- `pytest -q`

Results:

- Exported 756 replay decision rows from the completed backfilled six-month
  replay.
- Exported 213 trade rows and 211 next-event directional labels.
- Aggregate next-event directional accuracy: `0.4834`.
- Aggregate beat-SPY rate on scored trades: `0.4502`.
- Baseline logistic report:
  - train rows: 147, accuracy: `0.7347`.
  - validation rows: 31, accuracy: `0.4839`.
  - test rows: 33, accuracy: `0.4242`.
- Focused tests passed: `3 passed`.
- Full Python test suite passed: `213 passed, 1 skipped`.

Next recommended task:

- Historical note: at the time, the next task was to build replay/backtest
  standings API/UI. That was completed on 2026-08-19. The current next task is
  HOLD label improvement plus replay resume/chunk/progress controls.

Open questions:

- Should HOLD decisions get an explicit opportunity-cost label before training
  the next model?
- Should the next baseline target be `beat_benchmark_next_event`,
  `intent_mark_pnl_next_event > 0`, or a longer-horizon label?
- How should future actual replay cost fields be compared against no-orders
  intent PnL when provider usage is captured?

### 2026-08-18

Summary:

- Added sampled GDELT GKG archive backfill to the historical context exporter.
- Tightened GDELT ticker matching so company/ticker matches must appear in
  URL-derived headline/title text rather than only in GDELT body metadata.
- Built the backfilled six-month large-cap context and replay files.
- Ran the full backfilled six-month no-orders replay matrix for Claude and
  OpenAI across analyst, bear, and macro bots.
- Updated this handoff so the next agent starts from analysis/scoring, not
  data backfill or replay execution.

Files changed:

- `scripts/build_historical_context_export.py`
- `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
- `data/replay_runs/six_month_daily_backfilled_large_cap_report.json`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/session_notes/2026-08-18_gdelt_backfill_and_six_month_replay.md`

Commands run:

- `python scripts\build_historical_context_export.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL META AMZN TSLA AVGO AMD INTC ORCL CRM ADBE IBM NFLX NOW PLTR JPM BAC WFC GS MS C V MA AXP BLK SCHW LLY UNH JNJ ABBV MRK PFE TMO ABT ISRG AMGN WMT COST HD MCD SBUX NKE DIS KO PEP PG XOM CVX COP SLB CAT DE GE BA LMT RTX UPS FDX CMCSA T VZ --macro-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --include-sec --include-newsapi --newsapi-start 2026-07-18 --newsapi-max-per-ticker 5 --newsapi-page-size 5 --include-gdelt-gkg --gdelt-times-utc 130000 160000 200000 --gdelt-max-per-ticker 120 --gdelt-max-total 0 --gdelt-fetch-page-titles --gdelt-title-fetch-limit 300 --output data\replay_events\generated\historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json --report data\replay_events\generated\historical_context_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
- `python scripts\build_historical_replay_events.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL META AMZN TSLA AVGO AMD INTC ORCL CRM ADBE IBM NFLX NOW PLTR JPM BAC WFC GS MS C V MA AXP BLK SCHW LLY UNH JNJ ABBV MRK PFE TMO ABT ISRG AMGN WMT COST HD MCD SBUX NKE DIS KO PEP PG XOM CVX COP SLB CAT DE GE BA LMT RTX UPS FDX CMCSA T VZ --benchmarks SPY QQQ TLT GLD IEF IWM XLF XLK XLE XLV XLY --frequency 1d --news-mode historical-first --news-lookback-hours 96 --news-file data\replay_events\generated\historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json --output data\replay_events\generated\six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json --report data\replay_events\generated\six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
- `python scripts\run_replay_matrix.py --events data\replay_events\generated\six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --continue-on-error --report data\replay_runs\six_month_daily_backfilled_large_cap_report.json`
- `python -m py_compile scripts\build_historical_context_export.py scripts\build_historical_replay_events.py scripts\run_replay_matrix.py`
- `pytest -q`

Results:

- Backfilled context rows: 1,861 total.
- Backfilled context sources:
  - 1,266 GDELT GKG sampled public article rows after dedupe.
  - 560 SEC EDGAR filing rows.
  - 35 official macro-calendar rows.
- NewsAPI was rate-limited during this run and contributed 0 fresh rows.
- Backfilled replay file:
  - 126 market days.
  - 63 companies.
  - 11 ETF benchmarks.
  - dataset grade: `news_enriched`.
  - 5,494 real headline/context appearances.
  - 0 synthetic headline appearances.
  - 0 events below minimum headline coverage.
  - 0 no-lookahead violations.
  - 1 missing price row: `ABBV`.
- Six-month replay matrix:
  - report: `data/replay_runs/six_month_daily_backfilled_large_cap_report.json`
  - succeeded: 2
  - failed: 0
  - total decisions: 756
  - Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`
  - OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`
  - input fingerprint:
    `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`
- Local fixture scan showed 11 fixtures and 0 errors.
- Final full Python test suite passed: `210 passed, 1 skipped`.

Next recommended task:

- Inspect replay comparison/scoring for the two completed run IDs, then add
  benchmark-relative scoring and an ML-ready replay dataset exporter.

### 2026-08-18

Summary:

- Ran the one-month no-orders replay matrix for the mixed pilot input.
- Added `scripts/build_historical_context_export.py`.
- Researched historical news/context APIs and wired the locally available
  sources into an enriched context export.
- Built a 63-company large-cap six-month context file with SEC EDGAR, official
  macro-calendar, and partial NewsAPI context.
- Regenerated the full six-month replay input as `news_enriched`.

Files changed:

- `scripts/build_historical_context_export.py`
- `data/replay_runs/one_month_pilot_2026-07-18_2026-08-18_report.json`
- `data/replay_events/generated/historical_context_enriched_large_cap_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/historical_context_enriched_large_cap_2026-02-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/session_notes/2026-08-18_one_month_replay_and_large_cap_enrichment.md`

Commands run:

- `python scripts\run_replay_matrix.py --events data\replay_events\generated\one_month_pilot_2026-07-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --continue-on-error --report data\replay_runs\one_month_pilot_2026-07-18_2026-08-18_report.json`
- `python scripts\build_historical_context_export.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL META AMZN TSLA AVGO AMD INTC ORCL CRM ADBE IBM NFLX NOW PLTR JPM BAC WFC GS MS C V MA AXP BLK SCHW LLY UNH JNJ ABBV MRK PFE TMO ABT ISRG AMGN WMT COST HD MCD SBUX NKE DIS KO PEP PG XOM CVX COP SLB CAT DE GE BA LMT RTX UPS FDX CMCSA T VZ --macro-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --include-sec --include-newsapi --newsapi-start 2026-07-18 --newsapi-max-per-ticker 5 --newsapi-page-size 5 --output data\replay_events\generated\historical_context_enriched_large_cap_2026-02-18_2026-08-18.json --report data\replay_events\generated\historical_context_enriched_large_cap_2026-02-18_2026-08-18.report.json`
- `python scripts\build_historical_replay_events.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL META AMZN TSLA AVGO AMD INTC ORCL CRM ADBE IBM NFLX NOW PLTR JPM BAC WFC GS MS C V MA AXP BLK SCHW LLY UNH JNJ ABBV MRK PFE TMO ABT ISRG AMGN WMT COST HD MCD SBUX NKE DIS KO PEP PG XOM CVX COP SLB CAT DE GE BA LMT RTX UPS FDX CMCSA T VZ --benchmarks SPY QQQ TLT GLD IEF IWM XLF XLK XLE XLV XLY --frequency 1d --news-mode historical-first --news-lookback-hours 96 --news-file data\replay_events\generated\historical_context_enriched_large_cap_2026-02-18_2026-08-18.json --output data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json --report data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.report.json`
- `python scripts\run_replay_matrix.py --events data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --dry-run --report data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`

Results:

- One-month pilot replay succeeded: 2 commands, 2 completed, 0 failed, 132
  total decisions.
- One-month run IDs:
  - Claude: `5f0ea446-0c12-4655-90ff-f2cbe4bac453`
  - OpenAI: `c9a9b8dd-3e95-4224-be9b-ecf886c88306`
- Enriched context file contains 711 rows:
  - 560 SEC EDGAR filing rows
  - 116 NewsAPI article rows
  - 35 official macro-calendar rows
- Enriched six-month replay file:
  - 126 market days
  - 63 companies
  - 11 ETF benchmarks
  - dataset grade: `news_enriched`
  - 2,827 real headline/context appearances
  - 0 synthetic headline appearances
  - 0 no-lookahead violations
  - 1 missing price row: `ABBV` on `2026-08-11T21:00:00Z`
- Local fixture scan showed 10 fixtures, 0 errors, including the enriched
  generated file.
- Final full Python test suite passed: `210 passed, 1 skipped`.

Next recommended task:

- Add resume/skip/chunk controls before running the enriched six-month replay,
  then run the `six_month_daily_enriched_large_cap` no-orders matrix.

Open questions:

- Is the SEC-plus-partial-NewsAPI enriched file good enough to run the 756-call
  six-month replay now, or should a paid historical-news source be connected
  first?
- Should the one missing ABBV price row be tolerated, backfilled, or should ABBV
  be removed from the first large replay universe?

### 2026-08-18

Summary:

- Generated the first one-month and six-month historical replay input files.
- Used official Fed/BLS/BEA macro-calendar events as the real timestamped
  context source.
- Inspected both companion quality reports.
- Verified the six-month generated file loads through the replay workflow.
- Created a dry-run matrix report proving the actual replay commands can be
  generated without calling model providers.

Files changed:

- `data/replay_events/generated/historical_macro_context_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`
- `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json`
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.report.json`
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
- `api/routers/evaluation.py`
- `api/tests/test_evaluation_router.py`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/session_notes/2026-08-18_six_month_replay_input_generation.md`

Commands run:

- `python -m json.tool data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json > $null`
- `python scripts\build_historical_replay_events.py --start 2026-07-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL TSLA SPY QQQ TLT GLD IEF --benchmarks SPY QQQ TLT GLD --frequency 1d --news-mode historical-first --news-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --output data\replay_events\generated\one_month_pilot_2026-07-18_2026-08-18.json --report data\replay_events\generated\one_month_pilot_2026-07-18_2026-08-18.report.json`
- `python scripts\build_historical_replay_events.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL TSLA SPY QQQ TLT GLD IEF --benchmarks SPY QQQ TLT GLD --frequency 1d --news-mode historical-first --news-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --output data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.json --report data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.report.json`
- `python scripts\run_replay_matrix.py --events data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --dry-run --report data\replay_events\generated\six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
- `pytest -q api\tests\test_evaluation_router.py::test_list_replay_fixtures_summarizes_available_scenarios simulator\tests\test_historical_replay_event_builder.py -q`
- `python -c "import sys; sys.path[:0]=['simulator','.']; from api.routers import evaluation as e; r=e._load_replay_fixtures(); generated=[f['file_name'] for f in r['fixtures'] if f['file_name'].startswith('generated/')]; print({'fixture_count': len(r['fixtures']), 'error_count': len(r['errors']), 'generated': generated})"`
- `pytest -q`

Results:

- One-month input: 22 market-day events, yfinance prices, 42 real headline
  appearances, 206 synthetic headline appearances, 0 missing prices, 0 duplicate
  timestamps, 0 no-lookahead violations.
- Six-month input: 126 market-day events, yfinance prices, 238 real headline
  appearances, 1,209 synthetic headline appearances, 0 missing prices, 0
  duplicate timestamps, 0 no-lookahead violations.
- Six-month real-context day count: 33; synthetic-only day count: 93.
- Dataset grade for both generated files:
  `mixed_real_and_synthetic_context`.
- Local fixture scan: 9 replay fixtures, 0 errors; generated pilot and six-month
  files are listed, while the macro context source file is ignored.
- Focused tests passed: 5 tests.
- Full Python test suite passed: `210 passed, 1 skipped`.
- No actual replay/model-provider calls were run.

Next recommended task:

- Either run the one-month no-orders replay as a plumbing pilot, or enrich the
  historical context with timestamped ticker-specific news/SEC/earnings events
  before treating the replay as decision-grade ML evidence.

Open questions:

- Is macro-calendar plus synthetic context acceptable for the first no-orders
  pilot, or should ticker-specific historical news be added first?
- What real-context coverage threshold is required before six-month results can
  drive agent pruning?

### 2026-08-18

Summary:

- Implemented the first Phase 1 historical replay event builder.
- Added generated event quality reports and no-lookahead headline validation.
- Stabilized documented parser/outcome/evaluation-scheduler behavior so the
  full Python test suite passes.

Files changed:

- `scripts/build_historical_replay_events.py`
- `simulator/tests/test_historical_replay_event_builder.py`
- `simulator/replay_workflow.py`
- `api/routers/evaluation.py`
- `simulator/config.py`
- `simulator/bots/macro_bot.py`
- `simulator/base_bot.py`
- `simulator/reasoning_log.py`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/session_notes/2026-08-18_historical_event_builder.md`

Commands run:

- `python -m py_compile scripts/build_historical_replay_events.py simulator/replay_workflow.py api/routers/evaluation.py`
- `pytest -q simulator/tests/test_historical_replay_event_builder.py simulator/tests/test_replay_datasets.py api/tests/test_evaluation_router.py -q`
- `python scripts/build_historical_replay_events.py --start 2026-01-28 --end 2026-01-29 --tickers MSFT AAPL SPY --benchmarks SPY --price-file data/replay_events/sample_earnings_beat.json --news-mode synthetic --output "$env:TEMP\historical_replay_builder_smoke.json" --report "$env:TEMP\historical_replay_builder_smoke.report.json"`
- `pytest -q`

Results:

- Builder CLI smoke wrote a temp two-event synthetic-context replay file and
  report with zero no-lookahead violations.
- Full Python test suite passed: `210 passed, 1 skipped`.

Next recommended task:

- Create the one-month pilot dataset using `scripts/build_historical_replay_events.py`
  with real timestamped `--news-file` context if possible; inspect the report
  before running replay model calls.

Open questions:

- Which real news/calendar/SEC export should supply the first
  `--news-file`?
- What `min_headlines_per_event` threshold is sufficient before calling the
  pilot decision-grade?

### 2026-08-18

Created the agent playbook folder and added a detailed handoff structure.

Files added:

- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/01_ARCHITECTURE_AND_SYSTEM_DESIGN.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/05_AGENT_UPDATE_PROTOCOL.md`
- `docs/agent_playbook/06_INTERVIEW_SYSTEM_DESIGN_NOTES.md`
- `docs/agent_playbook/templates/TASK_NOTE_TEMPLATE.md`

Updated the playbook to capture the recurring evaluation loop:

- replay-first validation for ML, prompt, parser, and risk changes
- weekly or data-threshold-based evaluation of fresh live data
- ML dataset/report refreshes after meaningful new data or material fixes
- replay-regression checks before treating changes as improvements
