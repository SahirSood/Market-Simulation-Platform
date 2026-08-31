# Six-Month Replay Research Report

Generated: `2026-08-19T02:15:11.070136Z`
Benchmark: `SPY`

## Executive Summary

- Decisions analyzed: `756`.
- Trades: `213`; holds: `543`.
- BUY/SELL/HOLD mix: `2` / `211` / `543`.
- 1d directional accuracy on labeled trades: `48.34%`.
- 1d beat-benchmark rate on labeled trades: `45.02%`.
- 1d intent mark PnL: `-15,631.55`.
- HOLD rows that missed a >=2% one-day move somewhere in the universe: `539`.

## What Looks Good

- Best 1d intent PnL group is MacroBot (Claude) with 2 trades and PnL 378.00.
- Model suite trained for `directional_correct_1d`; best test-accuracy model was `extra_trees`.
- Model suite trained for `beat_benchmark_1d`; best test-accuracy model was `extra_trees`.
- Model suite trained for `beat_benchmark_3d`; best test-accuracy model was `logistic_regression`.
- Model suite trained for `high_confidence_wrong_1d`; best test-accuracy model was `random_forest`.

## What Looks Bad Or Risky

- Worst 1d intent PnL group is BearBot (OpenAI) with PnL -9,223.50.
- The aggregate 1d beat-benchmark rate is below 50%, so beating SPY is not proven yet.
- The bots held far more often than they traded; HOLD opportunity-cost labeling needs to improve before pruning quiet bots.
- For `directional_correct_3d`, the dummy majority baseline was hardest to beat on test accuracy; this target needs more data or better features.
- For `large_loss_1d`, the dummy majority baseline was hardest to beat on test accuracy; this target needs more data or better features.

## Bot / Provider Standings

| label | decision_count | trade_count | hold_count | directional_accuracy_1d | beat_benchmark_rate_1d | intent_mark_pnl_1d |
| --- | --- | --- | --- | --- | --- | --- |
| MacroBot (Claude) | 126 | 2 | 124 | 1.0000 | 0.0000 | 377.9997 |
| AnalystBot (Claude) | 126 | 0 | 126 |  |  |  |
| AnalystBot (OpenAI) | 126 | 0 | 126 |  |  |  |
| MacroBot (OpenAI) | 126 | 0 | 126 |  |  |  |
| BearBot (Claude) | 126 | 122 | 4 | 0.4959 | 0.4711 | -6786.0485 |
| BearBot (OpenAI) | 126 | 89 | 37 | 0.4545 | 0.4318 | -9223.4994 |

## Provider Standings

| label | decision_count | trade_count | directional_accuracy_1d | beat_benchmark_rate_1d | intent_mark_pnl_1d |
| --- | --- | --- | --- | --- | --- |
| claude | 378 | 124 | 0.5041 | 0.4634 | -6408.0489 |
| openai | 378 | 89 | 0.4545 | 0.4318 | -9223.4994 |

## Regime Standings

| label | decision_count | trade_count | directional_accuracy_1d | beat_benchmark_rate_1d | intent_mark_pnl_1d |
| --- | --- | --- | --- | --- | --- |
| risk_off | 48 | 14 | 0.5833 | 0.4167 | 1692.7998 |
| risk_on | 252 | 74 | 0.4189 | 0.3919 | -6519.9021 |
| neutral | 456 | 125 | 0.5120 | 0.4880 | -10804.4461 |

## Cost Snapshot

- Exact replay model cost is unavailable for this report because the source replay rows did not store token/cost fields.

## Model Suite Snapshot

- `directional_correct_1d`: best test-accuracy model `extra_trees`, best test-F1 model `extra_trees`, usable rows `211`.
- `beat_benchmark_1d`: best test-accuracy model `extra_trees`, best test-F1 model `extra_trees`, usable rows `211`.
- `directional_correct_3d`: best test-accuracy model `dummy_majority`, best test-F1 model `logistic_regression`, usable rows `207`.
- `beat_benchmark_3d`: best test-accuracy model `logistic_regression`, best test-F1 model `logistic_regression`, usable rows `207`.
- `large_loss_1d`: best test-accuracy model `dummy_majority`, best test-F1 model `logistic_regression`, usable rows `211`.
- `high_confidence_wrong_1d`: best test-accuracy model `random_forest`, best test-F1 model `random_forest`, usable rows `211`.

## Caveats

- This is replay/backtest evidence, not live trading history.
- The current run is no-orders mode, so intent PnL is not the same as fully executed PnL.
- GDELT backfill is sampled public metadata, not an exhaustive paid market-news feed.
- HOLD opportunity labels are coarse: they show missed market movement, not necessarily that a bot should have known the winning ticker.
- Model outputs are explanatory and exploratory until we add more labels, costs, and replay-regression validation.

## Recommended Next Actions

- Add product-facing replay standings API/UI from this analysis.
- Add cost aggregation before comparing providers as business choices.
- Improve HOLD opportunity labels and longer-horizon labels.
- Run selected intraday replay only after daily standings/reporting are useful.
