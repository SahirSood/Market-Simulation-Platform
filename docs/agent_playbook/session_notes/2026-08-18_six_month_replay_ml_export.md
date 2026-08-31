# Task Note

Date: 2026-08-18

Agent: Codex

Task: Export completed six-month replay to an ML dataset and train first baseline

## Summary

Completed the next useful work while the six-month replay finished:

- Confirmed the backfilled six-month replay completed for Claude and OpenAI.
- Added a replay ML dataset exporter.
- Added a feature dictionary writer.
- Added a lightweight logistic-regression baseline trainer.
- Exported the completed six-month replay to CSV.
- Trained the first exploratory directional-correct baseline report.
- Updated the playbook so future agents can continue from standings and
  analysis instead of rerunning the replay.

## Files Changed

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

## Commands Run

```powershell
python -m py_compile simulator\ml_dataset.py simulator\baseline_model.py scripts\export_ml_dataset.py scripts\train_baseline_evaluator.py
pytest -q simulator\tests\test_ml_dataset.py simulator\tests\test_baseline_model.py
python scripts\export_ml_dataset.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --output data\ml\datasets\replay_decisions_v1.csv --dictionary data\ml\datasets\feature_dictionary_v1.md --summary data\ml\datasets\replay_decisions_v1.summary.json
python scripts\train_baseline_evaluator.py --dataset data\ml\datasets\replay_decisions_v1.csv --target directional_correct_next_event --report data\ml\reports\baseline_logreg_directional_correct_v1.json --epochs 500 --min-rows 50
pytest -q
```

## Results

- Tests: focused ML tests passed, `3 passed`; full suite passed,
  `213 passed, 1 skipped`.
- Build: Python compile passed for the new modules/scripts.
- Data artifacts:
  - `data/ml/datasets/replay_decisions_v1.csv`
  - `data/ml/datasets/replay_decisions_v1.summary.json`
  - `data/ml/datasets/feature_dictionary_v1.md`
  - `data/ml/reports/baseline_logreg_directional_correct_v1.json`
- Replay run IDs:
  - Claude: `1a1ccc04-83d5-4943-803a-0b0916e33658`
  - OpenAI: `4de08543-6a78-4624-9aa8-7921d209ce75`
- Input fingerprint:
  - `913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329`
- Export summary:
  - 756 decision rows.
  - 213 trade rows.
  - 211 next-event directional labels.
  - aggregate next-event directional accuracy: `0.4834`.
  - aggregate beat-SPY rate: `0.4502`.
- First baseline:
  - train accuracy: `0.7347`.
  - validation accuracy: `0.4839`.
  - test accuracy: `0.4242`.

## Design Decisions

- The exporter writes one row per replay decision and keeps raw replay records
  unchanged.
- Future prices are written only to label columns and are marked as leakage risk
  in the feature dictionary.
- The first trainer is dependency-free so it can run in the current repo without
  adding an ML stack.
- The model split is time-ordered, not random, to avoid overstating results on a
  time-series replay dataset.

## Risks Or Caveats

- The first model is exploratory and not pruning-grade.
- Most scored trades are BearBot sells; AnalystBot mostly held, so the first
  directional target has limited signal for AnalystBot.
- HOLD decisions currently do not have an explicit opportunity-cost label.
- Historical note: replay cost aggregation and product-facing replay research
  API/UI were added on 2026-08-19. Exact cost is still unavailable for the old
  six-month run because its replay rows were recorded before replay cost fields
  existed.

## Next Recommended Task

- Improve HOLD opportunity-cost labels, then add replay resume/chunk/progress
  controls before larger replay batches.

## Open Questions

- Should the next label be `beat_benchmark_next_event`, longer-horizon PnL, or
  opportunity cost for HOLD decisions?
- Should `SPY` remain the default benchmark, or should `QQQ` and sector ETFs be
  included in the first standings view?
- How should future captured replay costs be weighed against intent PnL when
  comparing providers?
