# Session Note: Replay Research API/UI And Cost Capture

Date: 2026-08-19

## Summary

Implemented the product-facing layer for the v2 six-month replay research
artifacts and added replay cost/token capture for future replay runs.

## What Changed

- Added `GET /evaluation/replay-research?version=v2`.
- Added frontend `getReplayResearch()` API helper.
- Added the Six-Month Replay Research panel to the Evaluation page.
- Added replay decision fields:
  - `llm_input_tokens`
  - `llm_output_tokens`
  - `llm_total_tokens`
  - `llm_estimated_cost_usd`
- Added Alembic migration `0011_replay_llm_cost_tracking`.
- Added these fields to replay ML export as metric columns, not predictive
  features.
- Added cost snapshots to replay dataset summaries and Markdown research
  reports.
- Refreshed the v2 artifacts under `data/ml/`.

## Important Outcome

The current six-month replay still has no exact replay cost data:

- recorded cost rows: `0`
- missing cost rows: `756`

Reason:

The six-month replay was run before replay decisions stored token/cost fields.
The new code fixes future replay runs, but exact historical provider usage
cannot be reconstructed for old replay rows.

## Refreshed V2 Results

- rows: `756`
- trades: `213`
- HOLD rows: `543`
- 1d directional accuracy: `48.34%`
- 1d beat-SPY rate: `45.02%`
- 1d intent mark PnL: `-15,631.55`
- result quality: research-grade, not pruning-grade

## Verification

Commands:

```powershell
pytest -q simulator/tests/test_replay.py simulator/tests/test_ml_dataset.py simulator/tests/test_replay_research_models.py api/tests/test_evaluation_router.py api/tests/test_migrations.py
python scripts\refresh_replay_research.py --db sqlite:///replay.db --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 --benchmark SPY --version v2 --output-dir data\ml
cd frontend
npm run build
cd ..
pytest -q
```

Results:

- focused tests: `27 passed`
- frontend build: succeeded
- full tests: `216 passed, 1 skipped`

## Next Best Work

1. Improve HOLD opportunity labels.
2. Add replay resume/chunk/progress controls.
3. Add matrix dry-run cost estimates before larger replay batches.
4. Run richer agent-pruning analysis only after better labels and validation.
