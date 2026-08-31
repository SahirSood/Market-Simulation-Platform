# One-Month Replay And Large-Cap Enrichment

Date: 2026-08-18

Agent: Codex

Task: Run the one-month no-orders replay pilot and enrich the full six-month
replay input with many companies and real context.

Superseded status note: later on 2026-08-18, the six-month input was backfilled
with sampled GDELT GKG metadata and the full six-month no-orders replay matrix
completed. See
`docs/agent_playbook/session_notes/2026-08-18_gdelt_backfill_and_six_month_replay.md`.

## Summary

Completed both requested tracks:

- Ran the one-month no-orders replay matrix.
- Researched practical historical news/context APIs.
- Added a reusable context exporter.
- Built a 63-company enriched historical context file.
- Regenerated the full six-month replay input as `news_enriched`.

## Files Changed

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

## Commands Run

```powershell
python scripts\run_replay_matrix.py --events data\replay_events\generated\one_month_pilot_2026-07-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --continue-on-error --report data\replay_runs\one_month_pilot_2026-07-18_2026-08-18_report.json
```

```powershell
python scripts\build_historical_context_export.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL META AMZN TSLA AVGO AMD INTC ORCL CRM ADBE IBM NFLX NOW PLTR JPM BAC WFC GS MS C V MA AXP BLK SCHW LLY UNH JNJ ABBV MRK PFE TMO ABT ISRG AMGN WMT COST HD MCD SBUX NKE DIS KO PEP PG XOM CVX COP SLB CAT DE GE BA LMT RTX UPS FDX CMCSA T VZ --macro-file data\replay_events\generated\historical_macro_context_2026-02-18_2026-08-18.json --include-sec --include-newsapi --newsapi-start 2026-07-18 --newsapi-max-per-ticker 5 --newsapi-page-size 5 --output data\replay_events\generated\historical_context_enriched_large_cap_2026-02-18_2026-08-18.json --report data\replay_events\generated\historical_context_enriched_large_cap_2026-02-18_2026-08-18.report.json
```

```powershell
python scripts\build_historical_replay_events.py --start 2026-02-18 --end 2026-08-18 --tickers AAPL MSFT NVDA GOOGL META AMZN TSLA AVGO AMD INTC ORCL CRM ADBE IBM NFLX NOW PLTR JPM BAC WFC GS MS C V MA AXP BLK SCHW LLY UNH JNJ ABBV MRK PFE TMO ABT ISRG AMGN WMT COST HD MCD SBUX NKE DIS KO PEP PG XOM CVX COP SLB CAT DE GE BA LMT RTX UPS FDX CMCSA T VZ --benchmarks SPY QQQ TLT GLD IEF IWM XLF XLK XLE XLV XLY --frequency 1d --news-mode historical-first --news-lookback-hours 96 --news-file data\replay_events\generated\historical_context_enriched_large_cap_2026-02-18_2026-08-18.json --output data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json --report data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.report.json
```

```powershell
python scripts\run_replay_matrix.py --events data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json --provider-sets claude openai --bots analyst,bear,macro --no-orders --dry-run --report data\replay_events\generated\six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.replay_matrix_dry_run.report.json
```

## Results

One-month no-orders replay:

- Report: `data/replay_runs/one_month_pilot_2026-07-18_2026-08-18_report.json`
- Commands: 2.
- Succeeded: 2.
- Failed: 0.
- Claude run: `5f0ea446-0c12-4655-90ff-f2cbe4bac453`.
- OpenAI run: `c9a9b8dd-3e95-4224-be9b-ecf886c88306`.
- Decision count: 132 total.
- Input fingerprint:
  `646572652bd0e327b89d2774ff9b7cfc4b8099449a6cd4eec71a67c5a34ac070`.
- Execution mode: `--no-orders`.
- Native engine note: local engine adapter reported stub mode because the pybind
  extension is not built.

Verification:

- Full Python suite passed: `210 passed, 1 skipped`.
- Fixture scan found 10 fixtures and 0 errors.
- Generated fixture list includes:
  - `generated/one_month_pilot_2026-07-18_2026-08-18.json`
  - `generated/six_month_daily_2026-02-18_2026-08-18.json`
  - `generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`

Enriched context:

- Tickers: 63 companies.
- Context rows: 711.
- Sources:
  - SEC EDGAR: 560.
  - NewsAPI Everything: 116.
  - official macro calendar: 35.
- NewsAPI article sources after filtering:
  - Barchart.com
  - Benzinga
  - CNBC
  - GlobeNewswire
  - PRNewswire
  - TheStreet
  - Thefly.com
- NewsAPI caveat: current key/plan only allowed the 2026-07-18 through
  2026-08-18 slice and then hit a developer-plan rate limit.

Enriched six-month replay input:

- File:
  `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.json`
- Report:
  `data/replay_events/generated/six_month_daily_enriched_large_cap_2026-02-18_2026-08-18.report.json`
- Events: 126 market days.
- Tickers: 63 companies.
- Benchmarks: 11 ETFs.
- Dataset grade: `news_enriched`.
- Real headline/context appearances: 2,827.
- Synthetic headline appearances: 0.
- Events below minimum headline coverage: 0.
- Real-context days: 126.
- Synthetic-only days: 0.
- Unique real titles surfaced in replay events: 683.
- Missing prices: 1, `ABBV` on `2026-08-11T21:00:00Z`.
- Duplicate timestamps: 0.
- No-lookahead violations: 0.

## Source/API Research Notes

- SEC EDGAR is the best free six-month ticker-specific backbone currently wired.
- NewsAPI is useful but current local plan is limited for six-month historical
  replay.
- Strong future candidates to add with keys/plans:
  - Alpaca/Benzinga historical news.
  - Massive/Polygon ticker news.
  - Finnhub company news.
  - Tiingo news.
  - Marketaux entity-tagged financial news.
  - FMP stock news, press releases, and earnings calendars.

## Risks Or Caveats

- SEC filings are real and timestamped, but they are not the same as full market
  news coverage.
- NewsAPI coverage is partial because of plan/rate limits.
- The enriched file has one missing ABBV price row.
- The six-month replay itself has not been run yet. The dry-run report only
  records planned commands.
- Full enriched six-month replay is about 756 model calls:

```text
126 events x 3 bots x 2 providers = 756 calls
```

## Next Recommended Task

- Add resume/skip/chunk controls to `scripts/run_replay_matrix.py`.
- Then run the enriched six-month no-orders replay matrix.
- After that, inspect replay comparison metrics and begin benchmark-relative
  scoring / ML export.
