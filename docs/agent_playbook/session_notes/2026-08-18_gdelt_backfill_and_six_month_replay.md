# GDELT Backfill And Six-Month Replay

Date: 2026-08-18

## Summary

Backfilled the six-month replay context with sampled GDELT GKG archive rows,
regenerated the six-month large-cap replay file, inspected the quality report,
and ran the full no-orders replay matrix for Claude and OpenAI across analyst,
bear, and macro bots.

## Why This Was Needed

NewsAPI only covered the recent one-month slice under the current plan and was
rate-limited during this run. The first enriched six-month file had real SEC and
macro context, but the user wanted older real headline/news context too. GDELT
GKG raw archives provided a free public metadata backfill across the full
six-month window.

## Code Changed

- `scripts/build_historical_context_export.py`

Implemented sampled GDELT GKG support:

- `--include-gdelt-gkg`
- `--gdelt-times-utc`
- `--gdelt-domains`
- `--gdelt-max-per-ticker`
- `--gdelt-max-total`
- `--gdelt-pause-seconds`
- `--gdelt-fetch-page-titles`
- `--gdelt-title-fetch-limit`
- `--gdelt-title-pause-seconds`

Important quality fix:

- GDELT ticker matching now uses URL-derived headline/title text and the URL,
  instead of matching against broad GDELT body metadata. This avoids attaching
  an article to a ticker just because the company appeared somewhere in archive
  metadata.

## Generated Artifacts

- Context:
  `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.json`
- Context report:
  `data/replay_events/generated/historical_context_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
- Replay file:
  `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json`
- Replay report:
  `data/replay_events/generated/six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.report.json`
- Matrix report:
  `data/replay_runs/six_month_daily_backfilled_large_cap_report.json`

## Backfill Result

Context rows: 1,861 total.

Source breakdown:

- 1,266 GDELT GKG sampled public article rows after dedupe.
- 560 SEC EDGAR filing rows.
- 35 official macro-calendar rows.

NewsAPI result:

- Enabled, but rate-limited.
- 0 fresh rows contributed during this run.

GDELT result:

- 546 archive files attempted.
- 546 archive files downloaded.
- sampled UTC times: `13:00`, `16:00`, `20:00`.
- 300 page titles attempted.
- 215 page titles updated.
- 85 page title fetches failed.
- 0 GDELT archive errors.

## Replay File Quality

Backfilled replay file:

- 126 market days.
- 63 company tickers.
- 11 ETF benchmarks.
- dataset grade: `news_enriched`.
- 5,494 real headline/context appearances.
- 0 synthetic headline appearances.
- 0 events below minimum headline coverage.
- 0 no-lookahead violations.
- 0 duplicate timestamps.
- 1 missing price row: `ABBV`.

The replay file uses `trending_headlines`, `recent_headlines`,
`ticker_headlines`, and `source_events`. It does not use a plain `headlines`
field.

## Replay Matrix Result

Command:

```powershell
python scripts\run_replay_matrix.py --events data\replay_events\generated\six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --continue-on-error --report data\replay_runs\six_month_daily_backfilled_large_cap_report.json
```

Result:

- succeeded: 2
- failed: 0
- total decisions: 756
- Claude run: `1a1ccc04-83d5-4943-803a-0b0916e33658`
- OpenAI run: `4de08543-6a78-4624-9aa8-7921d209ce75`
- decisions per run: 378
- input fingerprint:
  `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`

Timing:

- Claude: `2026-08-18T22:30:29Z` to `2026-08-18T22:51:05Z`.
- OpenAI: `2026-08-18T22:51:05Z` to `2026-08-18T23:14:48Z`.

Operational warnings:

- Local engine adapter ran in stub mode because the native pybind extension was
  not built locally. This is acceptable for this run because `--no-orders` was
  used.
- One Claude BearBot LLM call emitted a JSON parse failure warning.
- Two OpenAI BearBot LLM calls hit model output-limit warnings.
- Despite those warnings, both provider commands completed and each produced all
  expected 378 decisions.

## Validation

Commands:

```powershell
python -m py_compile scripts\build_historical_context_export.py scripts\build_historical_replay_events.py scripts\run_replay_matrix.py
pytest -q
```

Results:

- Fixture scan: 11 fixtures, 0 errors.
- Full Python suite: `213 passed, 1 skipped`.

## Caveats

- GDELT is sampled, not exhaustive. This gives real six-month public headline
  metadata without a paid feed, but it is not equivalent to a complete
  market-news vendor tape.
- Some GDELT titles come from URL slugs when page titles could not be fetched.
- NewsAPI did not contribute fresh rows during the backfilled run because the
  configured developer-plan key was rate-limited.
- ABBV has one missing price row in the generated replay report.
- The full replay matrix was a direct long-running run, not resumable/chunked.

## Next

Start from product-facing analysis, not data generation:

1. Build a replay/backtest standings endpoint and UI section separate from live
   standings.
2. Move the SPY-relative labels now present in the ML export into reusable
   evaluation/API metrics.
3. Write a human-readable replay analysis report covering action mix,
   directional accuracy, intent PnL, SPY-relative results, holds, and caveats.
4. Add resume/chunk/progress controls before any larger intraday or
   prompt-version replay batch.
5. Treat the first baseline ML report as exploratory, not pruning-grade.
