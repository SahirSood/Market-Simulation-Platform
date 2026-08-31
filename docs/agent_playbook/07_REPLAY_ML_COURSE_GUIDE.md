# Replay ML Course Guide

Date: 2026-08-19

This guide explains the replay/ML system in plain language and in more technical
language. It is meant to help the user understand what the reports mean, why we
created each label/model, and how this becomes an improvement loop.

## The Simple Version

Imagine every bot is a student taking a daily test.

Each day, the bot gets a worksheet:

- prices
- market regime
- headlines
- SEC filings
- macro events
- its own portfolio state

The bot answers:

- BUY
- SELL
- HOLD
- ticker
- quantity
- confidence
- reasoning

After the day passes, we grade the answer using future prices.

The replay ML system is the gradebook plus the detective work. It asks:

- Which bots answer too often?
- Which bots never answer?
- Which bots are right in risk-off markets?
- Which bots lose money when they are confident?
- Which news/regime/ticker conditions usually lead to good decisions?
- Which conditions usually lead to bad decisions?

## Why Accuracy Is Not Enough

Accuracy means:

```text
Of the scored trade decisions, how many pointed in the right direction?
```

Example:

```text
Bot says SELL NVDA.
NVDA goes down tomorrow.
That is directionally correct.
```

But you are right to question this. Directional accuracy is not the only target.
A bot can be directionally correct and still not be a good strategy if:

- it makes tiny wins and huge losses
- it loses to simply holding SPY
- it trades too rarely
- it costs too much
- it is only right in one narrow regime

That is why v2 adds SPY-relative labels.

## Why SPY-Relative Targets Matter

SPY is our first benchmark for "the market."

The better question is often:

```text
Did the bot's idea beat just holding SPY over the same future window?
```

Example:

```text
Bot says BUY AAPL.
AAPL goes up 1%.
SPY goes up 2%.
```

Directional accuracy says:

```text
Correct, because AAPL went up.
```

SPY-relative scoring says:

```text
Not good enough, because SPY did better.
```

That is why we now use both:

- `directional_correct_1d`
- `beat_benchmark_1d`
- `intent_mark_pnl_1d`
- same idea for `3d` and `7d`

## What A Target Is

In machine learning, a target is the answer key.

The model sees features:

```text
bot type, provider, confidence, market regime, news counts, prior returns
```

Then it tries to predict a target:

```text
Was this trade correct?
Did this trade beat SPY?
Was this a large loss?
Was this a high-confidence mistake?
```

Without a target, the model has nothing to learn.

## Feature Columns Vs Label Columns

Feature columns are what the bot/model was allowed to know at decision time.

Examples:

- bot name
- provider
- confidence
- market regime
- headline counts
- ticker 5-day return
- volatility

Label columns use future data. They are for grading only.

Examples:

- future 1-day return
- future 3-day return
- beat SPY tomorrow
- future PnL

Important rule:

```text
Never train on label/future columns as features.
```

That would be cheating. It is called leakage.

## The Current Data

The current v2 dataset is:

- `data/ml/datasets/replay_decisions_v2.csv`

It contains:

- 756 replay decision rows
- 213 trade rows
- 543 HOLD rows
- 211 one-day labeled trade rows
- 0 recorded replay cost rows in the existing historical run

Why fewer labeled trades than trade rows?

Some trades happen near the end of the replay window. If there is no future
event available, we cannot honestly grade that horizon.

Why zero cost rows?

The six-month replay was run before replay decisions stored token/cost fields.
Live decisions already had cost tracking, but replay decisions were missing
those columns. The code now captures replay token/cost fields for future replay
runs, but it cannot reconstruct exact provider usage after the fact for the old
756 decisions.

## Current Scoring Results

The six-month replay produced:

- 1-day directional accuracy: `48.34%`
- 1-day beat-SPY rate: `45.02%`
- 1-day intent mark PnL: `-15,631.55`
- 3-day directional accuracy: `44.44%`
- 3-day beat-SPY rate: `43.96%`
- 7-day directional accuracy: `44.28%`
- 7-day beat-SPY rate: `41.79%`

Plain English:

```text
The current replayed trade decisions do not beat the market yet.
```

## What HOLD Means

HOLD is tricky.

If a bot says HOLD and nothing happens, that may be good.
If a bot says HOLD and a huge opportunity happens, that may be bad.

But this is hard because a HOLD row often does not pick a ticker.

The v2 exporter adds a coarse label:

- `hold_missed_big_move_1d`

It means:

```text
The bot held while at least one stock in the universe moved 2% or more the next day.
```

This is not proof the bot should have known the winner. It is an opportunity
smoke alarm. We need better HOLD labels later.

## Model Types We Now Run

The v2 model suite trains several models.

### Logistic Regression

Simple, explainable model.

Good for:

- first baseline
- feature direction
- "this feature pushes good/bad"

Weakness:

- mostly linear
- may miss combinations

### Random Forest

Many decision trees voting together.

Good for:

- nonlinear interactions
- "BearBot works only in risk-off plus high-volatility setups"
- feature importance

Weakness:

- can overfit if data is small
- less clean than logistic regression

### Extra Trees

Like Random Forest, but more randomized.

Good for:

- small/noisy tabular datasets
- finding robust-ish patterns

Weakness:

- still exploratory with only a few hundred trade labels

### Gradient Boosting

Trees trained sequentially, each trying to fix previous mistakes.

Good for:

- tabular prediction
- capturing interactions

Weakness:

- can overfit
- sensitive to small data

### Dummy Majority

This is the "stupid baseline."

It always predicts the most common class.

If the real models cannot beat this, that is a warning. It means:

- target is imbalanced
- data is too small
- features are weak
- or the pattern is not learnable yet

## Current Model Suite Interpretation

The best-looking v2 result:

- `beat_benchmark_1d`
- best test-accuracy model: Extra Trees
- test accuracy: about `69.7%`

This sounds good, but do not over-celebrate. The test set is small:

- only 33 rows for the 1-day test split

The honest interpretation:

```text
There may be useful signal for predicting whether trades beat SPY, but we need
more data and better validation before trusting it.
```

Some targets still have dummy-majority as the best test-accuracy model. That
means those targets are not reliably learnable yet.

## Architecture

The flow is:

```text
historical context + prices
-> replay event file
-> replay runs
-> replay decision rows
-> ML CSV export
-> scoring labels
-> model suite
-> standings JSON
-> Markdown research report
-> Evaluation page replay research panel
-> future GPT/agent review
```

Key files:

- `scripts/build_historical_context_export.py`
- `scripts/build_historical_replay_events.py`
- `scripts/run_replay_matrix.py`
- `scripts/export_ml_dataset.py`
- `scripts/train_model_suite.py`
- `scripts/analyze_replay_research.py`
- `scripts/refresh_replay_research.py`
- `api/routers/evaluation.py`
- `frontend/src/pages/EvalPage.jsx`

The main automation command is:

```powershell
python scripts/refresh_replay_research.py `
  --db sqlite:///replay.db `
  --input-fingerprint 913a986d59ffa5c7de375b5cfe0507c994b821d7550f59a2cb8c3602aee14329 `
  --benchmark SPY `
  --version v2 `
  --output-dir data/ml
```

This command does not call LLM providers. It is cheap. It refreshes analysis
from already-completed replay decisions.

## How This Becomes Self-Improvement Later

Do not let GPT blindly rewrite trading logic from one report.

The safer loop is:

1. Replay data creates scores.
2. ML/report explains weak spots.
3. GPT proposes a change.
4. The change gets a new prompt/model/version id.
5. Replay regression tests the change.
6. Promote only if the new version improves on honest metrics.
7. Then observe live data separately.

This is "incrementing."

It means each change must earn promotion.

## What We Still Need

Next useful work:

1. Better HOLD opportunity labels.
2. Matrix dry-run cost estimates before larger replay batches.
3. Replay resume/chunk/progress controls.
4. Longer-horizon labels with real trading-day meaning.
5. More replay rows from selected intraday days.
6. Prompt/model version registry.
7. A human agent-pruning report only after the above.

## Mental Model To Remember

The bots are not the final intelligence.

The evaluation system is the intelligence amplifier.

Replay gives us controlled evidence.
Scoring defines what good means.
ML finds patterns.
Reports tell us what to change.
Automation keeps the evidence fresh.

Only after all that should we let the system propose improvements.
