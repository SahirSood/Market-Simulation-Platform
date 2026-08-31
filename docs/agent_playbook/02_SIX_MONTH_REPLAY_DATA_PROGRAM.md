# Six-Month Replay Data Program

This document defines the plan for using replay to approximate six months of
bot trading behavior without waiting six real months.

## Goal

Collect a large, useful dataset for evaluation and ML.

The user wants to know:

- How would the current bots have traded over the past six months?
- Which bots perform best?
- Which providers perform best?
- Which prompts work best?
- Which market regimes expose weaknesses?
- Which decisions made money?
- Which decisions lost money?
- Which risk rejections saved us?
- Which risk rejections blocked good ideas?
- How does bot performance compare to the S&P 500 or SPY?
- Which bots should be kept when reducing the system from about 10 agents to
  about 6?

The replay feature is how we answer this without waiting six months.

The replay feature is also how we test changes before trusting them live. Any
meaningful prompt, parser, risk, scoring, or ML change should first be run
through a replay regression set. If a change performs worse on known replay
scenarios, treat it as a warning before allowing the live system to collect more
production-like data under that version.

Critical requirement:

Decision-grade replay must include news/event context. The live bots currently
trade from a combination of prices, broad market headlines, recent headlines,
ticker-specific headlines, RAG evidence, and portfolio state. A replay that only
contains prices does not test the same system. It mostly tests how bots react to
price movement summaries, which is useful for plumbing but not enough for ML
conclusions about real bot behavior.

Therefore:

- price-only replay is allowed only as a cheap smoke test
- the first serious one-month pilot should be news-enriched
- the six-month dataset should be news-enriched
- every headline/source must obey no-lookahead
- synthetic fallback text must be clearly marked as derived/synthetic

## Important Clarification

Replay does not magically create "real" six-month live trading history.

Replay creates a simulated history:

```text
Given historical inputs at time T, what would the current agent have decided?
```

That is extremely useful, but it must be labeled clearly as replay/backtest
data.

Do not overwrite live standings as if the bots actually ran live for six months.
Instead, create:

- Live standings
- Replay/backtest standings
- Combined research view, clearly labeled

## Six-Month Window

As of 2026-08-18, the requested lookback window is:

```text
2026-02-18 through 2026-08-18
```

Future agents should recompute this if the current date changes.

## Current Replay Capability

Already exists:

- JSON replay event fixtures.
- Replay price feed.
- Replay news feed.
- Replay bots using normal bot classes.
- Replay store.
- Replay run metadata.
- Input fingerprinting.
- Same-input provider comparison.
- Replay directional scoring.
- Replay matrix runner.
- Historical replay event builder.
- One-month and six-month generated replay input artifacts.
- Generated quality reports for replay input inspection.
- API endpoints for replay runs and comparisons.
- Evaluation UI for replay results.
- Benchmark-relative v2 replay scoring and ML export.
- Product-facing replay research endpoint:
  `GET /evaluation/replay-research?version=v2`.
- Evaluation page replay research panel.
- Replay decision token/cost field capture for future replay runs.

Missing:

- Exhaustive paid historical market-news coverage. The current preferred input
  uses SEC EDGAR, official macro calendars, and sampled GDELT public
  headline/URL metadata; it is real and no-lookahead, but not a complete vendor
  news tape.
- Historical price cache.
- Large-run orchestration with resume.
- Better HOLD/opportunity labels.
- Matrix dry-run cost estimates before large replay batches.
- Exact cost for the already-completed six-month replay; it cannot be
  reconstructed because the old replay rows were recorded before replay cost
  fields existed.

## What Counts As One Replay Event

A replay event is a timestamped market snapshot.

Current schema supports:

```json
{
  "timestamp": "2026-02-18T21:00:00Z",
  "prices": {
    "AAPL": 190.0,
    "MSFT": 420.0,
    "SPY": 510.0
  },
  "ohlcv": {
    "AAPL": {
      "open": 188.0,
      "high": 191.0,
      "low": 187.0,
      "close": 190.0,
      "volume": 50000000
    }
  },
  "trending_headlines": [],
  "recent_headlines": [],
  "ticker_headlines": {
    "AAPL": []
  },
  "expected_notes": []
}
```

For six-month replay, each event should include:

- timestamp
- price snapshot for tradable tickers
- OHLCV snapshot for each ticker
- benchmark prices
- broad market headlines available at or before the timestamp
- ticker-specific headlines available at or before the timestamp
- SEC/RAG evidence availability available at or before the timestamp
- market regime metadata
- event-source metadata
- no-lookahead evidence availability

## Data Sources

### Price Data

Current live system uses `yfinance` in `simulator/price_feed.py`.

Recommended first historical source:

- yfinance daily OHLCV for the configured tradable universe
- yfinance daily OHLCV for benchmarks

Why:

- cheap
- easy
- already aligned with the project
- enough to start daily replay

Known limitation:

- yfinance is not a professional market-data source
- for interviews, call it a prototype/free data adapter
- design should allow replacing it later

### Benchmark Data

Initial benchmark:

- `SPY`

Optional additional benchmarks:

- `^GSPC` for S&P 500 index
- `QQQ` for Nasdaq-like growth benchmark
- `TLT` for long-duration bonds
- `GLD` for gold
- equal-weight basket of tradable tickers
- cash baseline

Why `SPY` first:

- tradable ETF
- already in the project's ticker universe
- easy to compare bot portfolios against a buy-and-hold baseline

### News Data

Historical news is harder than price data, but it is not optional for the first
real ML/replay dataset.

Current NewsAPI-style sources may not provide reliable six-month historical
coverage under the current low-cost setup.

The reason this matters:

- AnalystBot is designed to trade from evidence and strong signals.
- BearBot searches for bearish interpretations of headlines.
- MacroBot ignores company-specific news and reacts to macro headlines.
- ContrarianBot uses price movement, but still benefits from market context.
- The live system passes `trending_headlines`, `recent_headlines`, and
  `ticker_headlines` into the prompt.

If generated replay events do not include news-like inputs, the replay will not
match how the current bots operate.

Recommended staged approach:

Stage 1:

- news-context discovery and a tiny generated sample
- inspect which historical news/event sources are available at low or no cost
- validate that every headline has a timestamp/source
- create a tiny event file with real or structured headlines

Stage 2:

- one-month daily pilot with news-enriched events
- include:
  - broad market headlines
  - ticker-specific headlines
  - macro calendar events
  - SEC/RAG filing context where available
  - benchmark prices
  - market regime features

Stage 3:

- six-month daily news-enriched dataset
- use price-derived synthetic summaries only when real headlines are missing
- mark every synthetic summary clearly in metadata

Stage 4:

- selected intraday news-enriched replay around major events
- prioritize high-volatility days and known macro/earnings dates

Allowed smoke test:

- price-only replay event summaries may be used to test file generation,
  validation, loading, and scoring
- this does not count as the real ML dataset
- use deterministic generated context such as:
  - "AAPL closed up 2.1% on high volume"
  - "SPY declined 1.4% as risk assets weakened"
  - "TLT rallied while QQQ sold off"

Preferred historical news/event sources:

- historical headlines from a low-cost/free provider if available
- SEC filings already in RAG, especially 10-K, 10-Q, and 8-K
- earnings calendars/results if timestamped and sourceable
- FOMC/CPI/PCE/jobs dates from public calendars
- company event metadata with timestamps
- price-derived market summaries only as a clearly marked fallback

Source/API findings from 2026-08-18:

- SEC EDGAR is the best free six-month ticker-specific backbone available now.
  Use official submissions metadata for timestamped 10-K, 10-Q, 8-K, 20-F, and
  6-K events.
- NewsAPI is configured locally through `NEWS_API_KEY`, but the current plan
  does not cover the whole six-month window. It allowed the 2026-07-18 through
  2026-08-18 slice before hitting developer-plan rate limits.
- GDELT GKG archive sampling is now implemented as the free six-month headline
  backfill path. It downloads raw GKG archive zip files for selected UTC times,
  filters to finance/business domains, derives titles from article URLs, and
  optionally fetches page titles. It is real public metadata and preserves
  `published_at`, `source`, `url`, and ticker tags.
- GDELT caveat: the current implementation samples three archive slices per day
  (`13:00`, `16:00`, `20:00` UTC). This is enough to make the daily six-month
  replay news-enriched without synthetic filler, but it is not an exhaustive
  historical news tape.
- Massive/Polygon-style ticker news is a strong future candidate because its
  news endpoint returns ticker-linked article metadata, publisher details,
  published UTC, sentiment/insights, and historical access depending on plan.
- Finnhub company news is a strong future candidate for North American
  companies; public docs/pricing describe one year of historical company news on
  lower tiers and deeper history on paid tiers.
- Alpaca historical news is a strong future candidate because its documentation
  says its news data is Benzinga-backed and dates back to 2015.
- Tiingo news is a strong future candidate for broad tagged historical coverage;
  its docs describe ticker tags, source domains, published dates, crawl dates,
  and a high daily article volume.
- Marketaux is a useful candidate for entity-tagged financial news and
  sentiment across many global sources/entities.
- FMP is worth considering for stock news, press releases, earnings calendars,
  and other market-calendar endpoints.

Current implemented source exporter:

```powershell
python scripts/build_historical_context_export.py `
  --start 2026-02-18 `
  --end 2026-08-18 `
  --tickers <company tickers> `
  --macro-file data/replay_events/generated/historical_macro_context_2026-02-18_2026-08-18.json `
  --include-sec `
  --include-newsapi `
  --newsapi-start 2026-07-18 `
  --include-gdelt-gkg `
  --gdelt-times-utc 130000 160000 200000 `
  --gdelt-max-per-ticker 120 `
  --gdelt-max-total 0 `
  --gdelt-fetch-page-titles `
  --gdelt-title-fetch-limit 300 `
  --output data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json `
  --report data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.report.json
```

Important:

Do not generate hindsight headlines like "stock fell because earnings missed" if
the bot would not have known that at the event timestamp. That creates leakage.

Minimum headline schema:

```json
{
  "title": "Fed leaves rates unchanged as officials cite sticky inflation",
  "source": "source name",
  "published_at": "2026-05-06T18:00:00Z",
  "url": "https://example.com/article",
  "age_minutes": 120,
  "age_label": "2h ago",
  "replay_source": "historical_news",
  "synthetic": false
}
```

For synthetic fallback:

```json
{
  "title": "SPY closed down 1.3% while TLT rose, indicating a risk-off session",
  "source": "generated_market_summary",
  "published_at": "2026-05-06T21:00:00Z",
  "url": "",
  "age_minutes": 0,
  "age_label": "replay",
  "replay_source": "derived_from_ohlcv",
  "synthetic": true
}
```

Synthetic summaries are acceptable only when they are derived from data available
at or before the event timestamp.

### RAG Evidence

The RAG system is useful for six-month replay if documents have correct
published timestamps.

During replay:

- use `AsOfRagRepository`
- set `as_of_date` to the event timestamp
- retrieve only evidence available at or before that date

This makes RAG replay defensible in an interview.

## Event Frequency Strategy

The user wants lots of data, but model calls cost money.

Use this staged frequency plan.

### Tier 0: Dry Planning

No model calls.

Build event files and validate them.

Outputs:

- generated replay JSON/JSONL
- data quality report
- event counts
- ticker coverage
- missing price report
- benchmark coverage report

### Tier 1: One-Month Daily Pilot

Goal:

- verify event quality
- verify no-lookahead rules
- estimate model costs
- test replay scoring

Approximate calls:

```text
21 trading days x 6 provider-specific bots = 126 model calls
```

This is small enough to inspect manually.

### Tier 2: Six-Month Daily Replay

Goal:

- establish first serious backtest dataset

Approximate calls:

```text
126 trading days x 6 provider-specific bots = 756 model calls
```

This is a reasonable first large run.

### Tier 3: Selected Intraday Replay

Goal:

- add richer data only around interesting days

Select days with:

- top 20 SPY absolute move days
- top 20 QQQ absolute move days
- top 20 high-volume days
- major macro event days
- major earnings/filing days

Frequency:

- market open
- midday
- close

Approximate calls:

```text
60 selected days x 3 events per day x 6 bots = 1,080 model calls
```

### Tier 4: Broad Intraday Replay

Only do this if costs are acceptable.

Example:

```text
126 trading days x 4 events per day x 6 bots = 3,024 model calls
```

Hourly or minute-level replay should not be the first approach.

## Replay-First Validation Loop

Every material change should go through this loop:

1. Run unit tests for the touched module.
2. Run a small replay regression set using existing fixtures.
3. Compare directional accuracy, intent PnL, risk-blocked PnL, citation rate,
   unsupported trade rate, and estimated model cost.
4. If the change is a prompt/model change, store it as a new prompt/model
   version rather than overwriting the old result.
5. Only after replay is acceptable should the change be considered ready for
   live-data observation.

Suggested initial replay regression set:

- `sample_earnings_beat.json`
- `sample_earnings_miss.json`
- `sample_fed_rate_shock.json`
- `sample_market_selloff.json`
- `sample_liquidity_rotation.json`
- `sample_sec_filing_risk.json`

Command shape:

```powershell
python scripts/run_replay_matrix.py `
  --events data/replay_events/sample_earnings_beat.json data/replay_events/sample_earnings_miss.json data/replay_events/sample_fed_rate_shock.json data/replay_events/sample_market_selloff.json data/replay_events/sample_liquidity_rotation.json data/replay_events/sample_sec_filing_risk.json `
  --provider-sets claude openai `
  --bots analyst,bear,macro `
  --db $env:DATABASE_URL `
  --no-orders `
  --continue-on-error `
  --report data/replay_runs/replay_regression_<version>.json
```

Future improvement:

- make this a first-class script such as `scripts/run_replay_regression.py`
- add `--baseline-report`
- add pass/fail thresholds
- add cost estimate before execution
- write a markdown summary for humans

## Ongoing Live-Data Evaluation Cadence

Six-month replay gives a large initial dataset, but the system should also learn
from new real data as the app runs.

Recommended cadence:

- Daily or hourly: outcome labeling, because this is cheap and already
  scheduler-friendly.
- Weekly: live-data evaluation report, if enough new decisions/outcomes exist.
- Data-threshold fallback: if a week has too little activity, wait until at
  least 50 new decisions or 50 new outcome labels exist.
- After every material fix: run replay regression immediately.
- After every prompt/model/risk change: run replay regression, then track live
  outcomes separately under the new version.
- Monthly: deeper review of agents, prompts, costs, benchmarks, and ML reports.

The weekly report should answer:

- How many new decisions were collected?
- How many new outcome labels were created?
- Did win rate improve or deteriorate?
- Did net PnL after estimated model cost improve?
- Did any bot become too expensive?
- Did citation rate improve?
- Did unsupported trade rate decrease?
- Did risk reject more trades?
- Did risk save losses or block winners?
- Did the live data agree with replay expectations?
- Should any agent be paused, modified, or promoted?

This should eventually become automated:

```text
new live decisions + new outcome labels + latest replay regression
-> weekly evaluation job
-> dataset refresh
-> metrics report
-> dashboard/API summary
-> next recommended actions
```

Do not use a weekly report as hard truth when the sample is tiny. Mark it as
"monitoring only" until enough observations exist.

## How To Get Immense Data Without Immense Token Cost

The trick is to separate expensive and cheap data.

Expensive:

- LLM decisions

Cheap:

- price movement labels
- benchmark labels
- volatility/regime features
- evidence availability counts
- risk-scoring simulations
- outcome labels at many horizons
- prompt metadata
- portfolio mark-to-market calculations

One LLM decision can create many training rows:

- next event direction
- 1-day return
- 3-day return
- 7-day return
- relative return vs SPY
- risk-adjusted return
- drawdown
- whether risk blocked it
- whether evidence existed
- whether confidence was calibrated

That means the dataset can be large even if model calls are controlled.

## Proposed Generated Data Layout

Recommended layout:

```text
data/
  replay_events/
    generated/
      six_month_daily_2026-02-18_2026-08-18.json
      six_month_daily_2026-02-18_2026-08-18.report.json
      one_month_pilot_2026-07-18_2026-08-18.json
      selected_intraday_2026-02-18_2026-08-18.json
```

Alternative if files become large:

```text
data/
  replay_events/
    generated/
      six_month_daily_2026-02-18_2026-08-18/
        manifest.json
        events_0001.jsonl
        events_0002.jsonl
        quality_report.json
```

Start with one JSON file because current replay code already supports it. Move
to shards if size becomes painful.

Current generated artifacts as of 2026-08-18:

- `data/replay_events/generated/historical_macro_context_2026-02-18_2026-08-18.json`
  - 35 official timestamped macro-calendar events from Federal Reserve, BLS,
    and BEA public release schedules.
- `data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json`
  - 22 market-day events.
  - report grade: `mixed_real_and_synthetic_context`.
  - 42 real headline appearances, 206 synthetic headline appearances.
  - 0 missing prices, 0 duplicate timestamps, 0 no-lookahead violations.
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json`
  - 126 market-day events.
  - report grade: `mixed_real_and_synthetic_context`.
  - 238 real headline appearances, 1,209 synthetic headline appearances.
  - 33 days with any real macro context, 93 synthetic-only days.
  - 0 missing prices, 0 duplicate timestamps, 0 no-lookahead violations.
- `data/replay_events/generated/historical_context_enriched_large_cap_2026-02-18_2026-08-18.json`
  - 63-company context file.
  - 711 real context rows:
    - 560 SEC EDGAR filings.
    - 116 NewsAPI finance/business article rows.
    - 35 official macro-calendar rows.
  - NewsAPI was limited to the 2026-07-18 through 2026-08-18 slice by the
    current key/plan and then hit developer-plan request limits.
- `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`
  - 126 market-day events.
  - 63 company tickers plus 11 ETF benchmarks.
  - report grade: `news_enriched`.
  - 2,827 real headline/context appearances, 0 synthetic appearances.
  - 126 days with real context, 0 synthetic-only days.
  - 1 missing price row: `ABBV` on `2026-08-11T21:00:00Z`.
  - 0 duplicate timestamps, 0 no-lookahead violations.
- `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - 63-company backfilled context file.
  - 1,861 real context rows:
    - 1,266 GDELT GKG sampled public article rows after dedupe.
    - 560 SEC EDGAR filing rows.
    - 35 official macro-calendar rows.
  - NewsAPI was rate-limited during this run and contributed 0 fresh rows.
  - GDELT sampling used three UTC archive slices per day and strict ticker
    matching against URL-derived headline/title text.
- `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`
  - 126 market-day events.
  - 63 company tickers plus 11 ETF benchmarks.
  - report grade: `news_enriched`.
  - 5,494 real headline/context appearances, 0 synthetic appearances.
  - 0 events below minimum headline coverage.
  - 1 missing price row: `ABBV`.
  - 0 duplicate timestamps, 0 no-lookahead violations.
- `data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
  - proves the matrix runner can produce planned no-order replay commands for
    Claude and OpenAI across analyst, bear, and macro bots.
  - dry run only; no model calls or replay decisions were made.
- `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json`
  - planned no-order replay commands for the enriched large-cap six-month file.
  - dry run only; no model calls or replay decisions were made.
- `data/replay_runs/six_month_daily_backfilled_large_cap_report.json`
  - completed no-orders replay matrix for the backfilled six-month file.
  - Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`.
  - OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`.
  - 756 total decisions, 2 succeeded commands, 0 failed commands.
  - input fingerprint:
    `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`.

Interpretation:

- The original mixed files remain useful for plumbing and comparison.
- The backfilled large-cap file is now the preferred six-month input because
  every event has real context, zero synthetic headline filler, and the full
  no-orders replay has already completed.
- Remaining quality caveats: the GDELT source is sampled rather than exhaustive,
  NewsAPI was rate-limited during the backfilled run, SEC filings are not the
  same as full market news, and there is one missing ABBV price row.

## Proposed Historical Event Builder

Add:

```text
scripts/build_historical_replay_events.py
```

Implementation status as of 2026-08-18:

- `scripts/build_historical_replay_events.py` exists.
- It can build daily `1d` replay JSON from yfinance, local price JSON, or an
  existing replay event JSON used as a price source for smoke tests.
- It supports local timestamped `--news-file` imports, plus `historical-first`,
  `news-file`, `synthetic`, and `price-only` modes.
- It writes a companion quality report with dataset grade, headline coverage,
  synthetic-vs-real counts, missing price counts, duplicate timestamps, and
  no-lookahead violation counts.
- The first one-month and six-month inputs have now been generated with official
  macro-calendar context plus synthetic fallback.
- `scripts/build_historical_context_export.py` now builds enriched local context
  from macro files, SEC EDGAR, NewsAPI metadata when available, and sampled
  GDELT GKG archive rows.
- A 63-company backfilled large-cap six-month input now exists and is the
  preferred replay input.
- The first full six-month no-orders replay has completed against that preferred
  input. The remaining data gap is quality/depth, not basic availability:
  replace or augment sampled GDELT with an exhaustive paid historical
  market-news feed if the project needs higher-fidelity news coverage.

Command shape:

```powershell
python scripts/build_historical_replay_events.py `
  --start 2026-02-18 `
  --end 2026-08-18 `
  --tickers AAPL MSFT NVDA GOOGL TSLA SPY QQQ TLT GLD IEF `
  --benchmarks SPY QQQ TLT GLD `
  --frequency 1d `
  --output data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.json `
  --report data/replay_events/generated/six_month_daily_2026-02-18_2026-08-18.report.json
```

Expected output event file:

- name
- description
- config
- events

Expected config fields:

- source: `historical_event_builder`
- start_date
- end_date
- frequency
- tickers
- benchmarks
- news_mode
- news_sources
- min_headlines_per_event
- synthetic_headline_policy
- generated_at
- data_provider
- no_lookahead_policy
- event_count
- trading_day_count
- missing_data_summary
- news_coverage_summary

Each event should include:

- timestamp
- prices
- ohlcv
- benchmark_prices
- benchmark_returns
- market_regime
- recent_headlines
- trending_headlines
- ticker_headlines
- source_events
- news_coverage
- generated_features
- expected_notes

## Market Regime Features

Add deterministic features that do not require LLM calls:

Per ticker:

- daily return
- 5-day return
- 20-day return
- rolling volatility
- volume ratio
- gap from previous close
- distance from 20-day moving average

Market-wide:

- SPY daily return
- QQQ daily return
- TLT daily return
- GLD daily return
- risk-on/risk-off flag
- volatility bucket
- trend bucket
- breadth proxy from tradable universe

Example `market_regime`:

```json
{
  "date": "2026-05-12",
  "spy_return_1d": -0.013,
  "qqq_return_1d": -0.018,
  "tlt_return_1d": 0.006,
  "risk_regime": "risk_off",
  "trend_regime": "down",
  "volatility_regime": "high"
}
```

These features are useful for ML and for prompt context.

## Generated Event Text Without Leakage

If no historical headline is available, generate plain market-state summaries
from data available at that point.

Safe examples:

- "SPY is down 1.3% today with weakness across large-cap growth."
- "TLT is up 0.6% while QQQ is down 1.8%, suggesting risk-off positioning."
- "NVDA is trading above its 20-day average after a 3-day rally."

Unsafe examples:

- "The stock will recover tomorrow."
- "The market sold off before a Fed surprise next week."
- "AAPL fell because earnings missed" when the earnings result was not yet
  published.

Rule:

Every generated line must be derivable from data at or before the timestamp.

## Replay Run Strategy

### Pilot Run

Run one month first:

```powershell
python scripts/run_replay_matrix.py `
  --events data/replay_events/generated/one_month_pilot_2026-07-18_2026-08-18.json `
  --provider-sets claude openai `
  --bots analyst,bear,macro `
  --db $env:DATABASE_URL `
  --no-orders `
  --report data/replay_runs/one_month_pilot_report.json
```

Inspect:

- run completed
- decision count matches expectation
- no parser failures
- token/cost estimates
- replay comparison metrics
- whether bots only HOLD
- whether generated context is too weak

### Six-Month Daily Run

Completed on 2026-08-18 against the preferred backfilled input:

```powershell
python scripts/run_replay_matrix.py `
  --events data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json `
  --provider-sets claude openai `
  --bots analyst,bear,macro `
  --db $env:DATABASE_URL `
  --no-orders `
  --continue-on-error `
  --report data/replay_runs/six_month_daily_backfilled_large_cap_report.json
```

Result:

- Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`.
- OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`.
- 756 total decisions.
- 2 succeeded commands, 0 failed commands.
- Input fingerprint:
  `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`.

### Execution Mode

Use `--no-orders` first.

Why:

- cheaper operationally
- isolates decision quality from engine liquidity issues
- lets us score intent PnL
- avoids confusing early data with stub/native engine differences

Later, run execution-enabled replay:

```powershell
python scripts/run_replay_matrix.py `
  --events data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json `
  --provider-sets claude openai `
  --bots analyst,bear,macro `
  --db $env:DATABASE_URL `
  --report data/replay_runs/six_month_daily_execution_report.json
```

Do this only after engine/liquidity assumptions are clear.

## Replay Standings Design

Do not update live standings directly.

Add a separate replay standings concept:

```text
GET /evaluation/replay-standings?window=six_month_daily&benchmark=SPY
```

Possible UI labels:

- Live Leaderboard
- Six-Month Replay Standings
- Backtest Standings
- Prompt Experiment Results

Fields:

- bot_id
- bot_name
- provider
- prompt_version
- replay_window
- run_count
- decision_count
- trade_count
- hold_count
- directional_accuracy
- intent_mark_pnl
- approved_intent_mark_pnl
- risk_blocked_mark_pnl
- benchmark_return
- excess_return_vs_spy
- max_drawdown
- estimated_llm_cost
- net_after_llm_cost
- unsupported_trade_rate
- citation_rate
- avg_confidence

Reason:

Live and replay data answer different questions.

Live:

```text
What happened while the system actually ran?
```

Replay:

```text
What would the current system do on past inputs?
```

Both are useful, but they should be separate.

## Benchmark Comparison

Initial benchmark:

```text
Buy and hold SPY over the same replay window.
```

For every replay run, compute:

- starting SPY price
- ending SPY price
- SPY return
- equivalent portfolio value if starting cash bought SPY
- bot replay portfolio value or intent value
- excess return:

```text
bot_return - spy_return
```

Also compute:

- win rate vs SPY by event
- correlation to SPY
- beta-like exposure estimate
- drawdown vs SPY drawdown

Do not overcomplicate this before the data exists. Start with SPY return and
excess return.

## Resume And Idempotency Requirements

Large replay runs need resume.

Required behavior:

- if a run already exists for the same event file, provider set, bot set, prompt
  version, and model config, do not accidentally duplicate unless explicitly
  requested
- store a run manifest
- store command args without secrets
- support chunking by date
- support `--resume`
- support `--skip-existing`
- support `--max-events`
- support `--start-index`
- support `--end-index`

Why:

Six-month replay can take time and money. Losing progress halfway through would
be painful.

## Validation Requirements

Add tests that verify generated events:

- are valid JSON
- have monotonically increasing timestamps
- include prices
- include benchmark prices
- include SPY unless explicitly disabled
- include news/event context for decision-grade datasets
- mark price-only files as smoke-test datasets
- do not include headlines with `published_at` after the event timestamp
- distinguish real historical headlines from synthetic market summaries
- do not include future timestamps out of order
- contain no raw secrets
- contain metadata describing source and window
- can be loaded by `load_replay_event_file`

Add data quality report:

- event count
- ticker count
- missing ticker/date pairs
- earliest timestamp
- latest timestamp
- benchmark coverage
- headline coverage
- real headline count
- synthetic headline count
- events below minimum headline coverage
- dropped rows
- duplicate timestamps

## ML Readiness

The six-month replay data should be built to support ML export.

Every replay decision should be joinable to:

- event timestamp
- ticker prices
- benchmark prices
- headline context
- headline source metadata
- synthetic-vs-real headline flags
- market regime
- bot identity
- provider identity
- prompt version
- model hash
- risk limits
- evidence ids
- action
- confidence
- outcome labels

This enables supervised learning:

```text
features at decision time -> future outcome
```

## Recommended Implementation Order

1. Create generated replay events folder.
2. Choose the minimum viable historical news/event context source.
3. Build daily historical event generator with news mode.
4. Add event validation tests, including no-lookahead headline tests.
5. Generate a tiny news-enriched sample.
6. Generate one-month news-enriched pilot. `Done structurally; context is mixed.`
7. Run one-month pilot with no orders.
8. Generate six-month daily news-enriched dataset. `Done with backfilled
   large-cap context.`
9. Run six-month daily replay. `Done for Claude/OpenAI analyst, bear, and macro
   bots in no-orders mode.`
10. Add benchmark-relative replay scoring.
11. Add replay standings endpoint.
12. Add replay standings UI.
13. Export ML dataset.
14. Train baseline ML model.
15. Use findings to prune/adjust agents.
16. Add replay regression automation for future fixes.
17. Add weekly/data-threshold live-data evaluation reports.
18. Refresh ML datasets and reports on a recurring cadence.
