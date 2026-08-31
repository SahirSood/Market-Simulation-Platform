# Replay Research V2 Models And Refresh

Date: 2026-08-18

Agent: Codex

Task: Build richer scoring, standings, multi-model ML reports, automated refresh,
and a course-style guide for the completed six-month replay.

## Summary

Added the v2 replay research layer on top of the completed six-month backfilled
replay. This does not call LLM providers. It consumes completed replay decisions
and regenerates labels, models, standings, and reports.

## Files Changed

- `simulator/ml_dataset.py`
- `simulator/baseline_model.py`
- `simulator/model_suite.py`
- `simulator/replay_research.py`
- `scripts/train_model_suite.py`
- `scripts/analyze_replay_research.py`
- `scripts/refresh_replay_research.py`
- `simulator/tests/test_ml_dataset.py`
- `simulator/tests/test_replay_research_models.py`
- `requirements.txt`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/07_REPLAY_ML_COURSE_GUIDE.md`
- `docs/agent_playbook/session_notes/2026-08-18_replay_research_v2_models_and_refresh.md`

## New Artifacts

- `data/ml/datasets/replay_decisions_v2.csv`
- `data/ml/datasets/replay_decisions_v2.summary.json`
- `data/ml/datasets/feature_dictionary_v2.md`
- `data/ml/reports/model_suite_v2.json`
- `data/ml/reports/replay_standings_v2.json`
- `data/ml/reports/replay_research_report_v2.md`
- `data/ml/reports/refresh_manifest_v2.json`

## What V2 Adds

- 1d, 3d, and 7d future labels.
- SPY-relative labels:
  - `beat_benchmark_1d`
  - `beat_benchmark_3d`
  - `beat_benchmark_7d`
- Intent PnL labels by horizon.
- Large-loss labels.
- High-confidence-wrong labels.
- Coarse HOLD missed-opportunity labels.
- Replay standings by bot/provider, provider, personality, action, regime,
  volatility, confidence bucket, and news quality.
- Multi-model suite:
  - logistic regression
  - random forest
  - extra trees
  - gradient boosting
  - dummy-majority baseline
- One-command cheap refresh:

```powershell
python scripts\refresh_replay_research.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --version v2 --output-dir data\ml
```

## V2 Results

- Rows: 756 replay decisions.
- Trades: 213.
- HOLD rows: 543.
- 1d labeled trades: 211.
- 1d directional accuracy: `0.4834`.
- 1d beat-SPY rate: `0.4502`.
- 1d intent mark PnL: `-15631.548299`.
- 3d directional accuracy: `0.4444`.
- 3d beat-SPY rate: `0.4396`.
- 3d intent mark PnL: `-22530.248187`.
- 7d directional accuracy: `0.4428`.
- 7d beat-SPY rate: `0.4179`.
- 7d intent mark PnL: `-54197.800866`.

Model suite highlights:

- `directional_correct_1d`: best test-accuracy model `extra_trees`, accuracy
  `0.6061`.
- `beat_benchmark_1d`: best test-accuracy model `extra_trees`, accuracy
  `0.6970`.
- `beat_benchmark_3d`: best test-accuracy model `logistic_regression`, accuracy
  `0.6875`.

Interpretation:

- The current replay decisions do not prove market-beating behavior.
- There may be useful signal for SPY-relative prediction, but test splits are
  small and should be treated as research, not production trading rules.
- BearBot made nearly all trades; AnalystBot and MacroBot mostly held.
- HOLD labels are still crude and must be improved before pruning quiet bots.

## Validation

Commands run:

```powershell
python -m py_compile simulator\ml_dataset.py simulator\baseline_model.py simulator\model_suite.py simulator\replay_research.py scripts\train_model_suite.py scripts\analyze_replay_research.py scripts\refresh_replay_research.py scripts\export_ml_dataset.py scripts\train_baseline_evaluator.py
pytest -q simulator\tests\test_ml_dataset.py simulator\tests\test_baseline_model.py simulator\tests\test_replay_research_models.py
python scripts\refresh_replay_research.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --version v2 --output-dir data\ml
pytest -q
```

Focused tests: `4 passed`.
Full Python suite: `214 passed, 1 skipped`.

## Next

Superseded on 2026-08-19:

- API/UI for the v2 replay research artifacts now exists.
- Replay token/cost capture now exists for future replay rows.
- The refreshed v2 report now explicitly shows cost unavailable for the old
  six-month run because its rows were recorded before replay cost fields
  existed.

Remaining current next work:

1. Improve HOLD opportunity-cost labels.
2. Add report-to-report comparisons in the refresh manifest.
3. Add replay resume/chunk/progress controls before larger intraday replays.
4. Add matrix dry-run cost estimates before larger replay batches.
