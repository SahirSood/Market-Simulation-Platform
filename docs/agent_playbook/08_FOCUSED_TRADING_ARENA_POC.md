# Focused Trading Arena POC

Date: 2026-08-31

This document records the corrected product direction after the brief-first
plan was rejected.

The project should remain a trading simulation and evaluation platform. The
investment-style recap is useful, but it is not the product by itself. The C++
order book, live/simulated orders, fills, portfolios, RAG evidence, MCP-style
tools, risk controls, replay, benchmarks, and ML evaluation should stay central.

The corrected direction is:

```text
Build a focused AI infrastructure trading arena that shows what agents trade,
why they trade it, how those orders move through risk and the order book, and
whether the behavior is better than benchmarks.
```

## Why The Direction Changed

The previous planning pass overcorrected. It correctly noticed that the project
was too broad and needed a clearer "so what," but it made the investment brief
the main product. That is not the intended product.

The user wants the system to keep trading. The point of narrowing is not to
remove the trading arena. The point is to make the arena easier to understand,
evaluate, and improve.

Narrowing to one universe helps because:

- bot decisions become comparable across the same market context
- RAG/evidence can be tuned around one coherent domain
- benchmarks are easier to explain
- replay results are easier to interpret
- prompt changes can be tested in a controlled way
- the user can personally learn why the bots buy, sell, hold, or get rejected
- expansion to other sectors can happen only after this first universe works

## POC North Star

The first POC should answer:

```text
In the AI infrastructure / large-cap technology universe, what are the agents
trading, why are they trading it, what happened in the simulated market, and how
does that compare to benchmarks?
```

This is a trading product with an explanatory layer, not a research memo with
trading hidden underneath.

## Initial Universe

Start narrow.

First tradable universe:

- `NVDA`
- `AMD`
- `AVGO`
- `MSFT`
- `GOOGL`
- `AMZN`
- `TSLA`

First benchmark universe:

- `SPY`
- `QQQ`
- `SMH` later, after it is cleanly added to price, replay, and scoring

The broader 63-company replay dataset remains useful as research data, but the
first live product should not ask users to inspect every sector at once.

## Primary User Experience

The root route should not be a standalone brief. The root route should be a
focused trading arena.

Suggested first-screen order:

1. Trading graph / portfolio value / benchmark comparison.
2. Current focused-universe market strip.
3. Latest bot decisions and live order/fill activity.
4. Position, PnL, exposure, and risk-rejection summary.
5. Short recap or investment-style explanation underneath the graph.
6. Agent reasoning and cited evidence drilldown.
7. Links or tabs into the deeper `/research` workbench.

The recap/brief should explain the trading, not replace it.

## Role Of The Recap/Brief

Keep the recap. It is valuable for the user's personal learning and for a
recruiter-friendly "so what."

But the recap should live under the graph or within the arena, answering:

- what changed in the focused universe
- what trades happened or were proposed
- why the agents acted
- which evidence or news mattered
- what risk controls blocked
- whether the bots beat or lagged `SPY` and `QQQ`
- what would change the bot view

The existing `GET /evaluation/decision-brief` endpoint and `BriefPage` are not
wasted. They should be repositioned into an arena recap component or subroute
instead of being the whole root product.

## Essential Live Agents

For the first focused arena, keep three serious perspectives across both
providers:

- AnalystBot: evidence and company-specific thesis.
- MacroBot: rates, liquidity, market regime, and ETF/benchmark context.
- BearBot: downside case, valuation risk, fragility, and counterargument.

This creates six provider-specific live agents:

- AnalystBot with Claude
- AnalystBot with OpenAI
- MacroBot with Claude
- MacroBot with OpenAI
- BearBot with Claude
- BearBot with OpenAI

That is enough diversity to see meaningful disagreement without making the
arena noisy.

## Parked Agents

Do not delete these agents:

- DegenBot
- ContrarianBot

They should remain available for:

- sandbox demos
- replay experiments
- future strategy comparisons
- later reintroduction if evidence supports them

They are parked from the first serious live arena because the first goal is to
understand and improve a smaller, cleaner agent set.

## What The Main Arena Should Show

The primary product surface should expose the trading machinery clearly:

- live/simulated portfolio value by bot and provider
- benchmark lines for `SPY` and `QQQ`
- focused-universe ticker performance
- current positions and cash
- open orders and recent fills
- risk rejections and reasons
- action mix: BUY, SELL, HOLD
- cost usage and budget status
- evidence/citation status
- latest bot rationale
- replay/backtest comparison, clearly labeled separately from live results

The UI can still be simple. Simplification means fewer top-level routes and a
clearer hierarchy, not removing the trading mechanics.

## Research Workbench

The `/research` route should remain the deeper tabbed area.

Tabs should include:

- Evidence/RAG
- Evaluation
- Bots
- Order Book
- Behavior
- Config

This is the right place for detailed diagnostics, fixture libraries, exports,
retrieval metrics, replay research, bot timelines, and configuration surfaces.

## ML Role

Continue ML, but keep it as evaluation and trust analysis.

The useful ML question is:

```text
When should we trust or distrust a bot's trade proposal in this focused market?
```

ML should help:

- detect high-confidence wrong trades
- compare providers and bots by regime
- score trades against `SPY`, `QQQ`, and later `SMH`
- identify when HOLD missed opportunity
- evaluate prompt changes
- eventually support an advisory meta-evaluator

ML should not replace the trading agents yet.

## What To Deprioritize

Near-term deprioritized work:

- adding every sector
- adding more primary live bot personalities
- broad intraday replay before daily focused replay is useful
- options
- production-grade short-selling mechanics
- more ML model types for their own sake
- making a standalone research brief the root product
- polishing every old dashboard equally

Keep the code for these areas where useful, but the first POC should be the
focused trading arena.

## Immediate Build Sequence

1. Update planning docs to correct the hierarchy: arena first, recap underneath.
2. Rebuild the root route so it starts with the focused trading graph and
   benchmark comparison.
3. Move or reuse the existing brief page as an embedded recap below the main
   trading graph.
4. Keep `/research` as the simplified deeper tabbed workbench.
5. Verify the core six agents still trade only the focused universe.
6. Run a focused live loop during market hours and inspect actual decisions,
   orders, fills, risk rejections, and evidence.
7. Tune prompts and evidence retrieval for the focused universe.
8. Add HOLD opportunity-cost labels and replay cost/resume controls.
9. Run focused news-enriched replay/regression before expanding.

## Definition Of Done For The POC

The POC is useful when a user can open the app and quickly understand:

- which bots are active
- what each bot traded, held, or tried to trade
- how approved orders flowed through risk and the C++ order book
- current portfolio value, positions, cash, fills, and PnL
- whether the bot behavior is beating or lagging `SPY` and `QQQ`
- which evidence or market context drove decisions
- why risk controls blocked certain orders
- what the recap says about the current market state
- whether replay/live evidence suggests the agents are improving

This should feel like a serious narrowed market-simulation lab with a helpful
explanation layer.
