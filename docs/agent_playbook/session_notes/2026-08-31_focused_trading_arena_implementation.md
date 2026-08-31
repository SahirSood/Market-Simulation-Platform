# Focused Trading Arena Implementation

Date: 2026-08-31

Agent: Codex

## Summary

Implemented the corrected trading-first product hierarchy end to end.

- Root `/` now renders the focused tech trading arena.
- `/brief` remains a secondary full market recap.
- `/research` remains the tabbed Evidence, Evaluation, Bots, Order Book,
  Behavior, and Config workbench.
- Added a selected-ticker market graph against `SPY` and `QQQ` using normalized
  replay history returned by `GET /evaluation/decision-brief`.
- Placed the compact market recap and Analyst/Macro/Bear views directly under
  the graph.
- Preserved the live portfolio comparison graph, decision/order/fill tape,
  public-safe RAG/MCP/risk/execution activity, and evidence/cost controls.
- Added compact open-position and selected-ticker order-book panels.
- Updated the UI from five strategies/ten bots to the active six-agent cohort.
- Made the arena recap skip slower deep evidence retrieval; `/brief` keeps the
  full evidence-backed response.
- Removed unnecessary `Content-Type` headers from GET requests and added both
  localhost forms to local CORS defaults.
- Built the native C++ pybind module locally, replacing stub-mode books with
  seeded bid/ask depth.
- Structured HOLD causes now travel through the decision contract, live
  persistence, replay persistence, evaluation summaries, activity metadata,
  WebSocket events, and the live tape/behavior UI.
- The live portfolio graph now hydrates persisted BUY/SELL/HOLD activity and
  overlays markers without mixing individual decisions into team performance.
- MacroBot now trades only focused technology names; `SPY` and `QQQ` remain
  benchmark context rather than trade targets.
- Long-lived PostgreSQL pools now pre-ping and recycle idle connections so the
  public API can recover from database connection expiry.

## Verification

- Frontend production build passed.
- Final full backend suite passed: `226 passed`.
- Native C++ test suite passed: `10/10`.
- Python bridge smoke confirmed native mode with three bid and three ask levels.
- Live API smoke confirmed six bots, 126 chart points, and native book depth.
- Desktop browser check rendered both graphs and the recap with live API data.
- Mobile browser check rendered at a narrow viewport without horizontal page
  overflow.
- Ticker switching from `NVDA` to `AMD` updated price, benchmark, and recap
  state.

## Remaining Work

- Build the weekly or threshold-based evaluation report.
- Collect a clean live decision/outcome window before making benchmark claims.
- Improve HOLD opportunity-cost labels and add replay resume/chunk controls
  before another expensive replay batch.

## Live evaluation report follow-up

The weekly/threshold report is now implemented in
`simulator/live_evaluation.py`, with API, CLI, Evaluation-page, and scheduler
integration. It reads stored live decisions and outcomes without making LLM
calls, reports bot/provider/prompt-version behavior and estimated spend, and
stays `monitoring_only` until the selected horizon reaches 50 labeled
decisions. Benchmark and same-input replay comparisons are explicitly marked
data-limited until their live snapshots/baselines are persisted.

Focused verification for this follow-up: `27 passed`.

Remaining work is to collect a clean live window and let new decisions age into
1d labels. New immediate outcomes now persist SPY/QQQ prices, so the report can
make benchmark claims once those labeled rows exist rather than relying on the
current replay-only artifacts.
