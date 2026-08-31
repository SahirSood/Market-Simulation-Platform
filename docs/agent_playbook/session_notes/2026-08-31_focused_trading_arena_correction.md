# Focused Trading Arena Direction Correction

Date: 2026-08-31

Agent: Codex

Task:

Correct the planning docs after the user rejected the brief-first framing. The
project should remain a trading simulation and evaluation platform, but the
first product scope should be narrower and easier to understand.

## Summary

Completed:

- Reframed the immediate product as a focused AI infrastructure / large-cap
  technology trading arena, not a standalone investment brief.
- Preserved the core architecture goals:
  - C++ order book and matching path
  - simulated BUY/SELL/HOLD decisions
  - risk checks, orders, fills, positions, and PnL
  - RAG/evidence retrieval
  - MCP-style agent tools
  - replay/evaluation
  - ML labels and interpretation
- Kept the first tradable universe narrow:
  `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, and `TSLA`.
- Kept first benchmarks as `SPY` and `QQQ`, with `SMH` deferred until the data
  and replay pipeline support it cleanly.
- Clarified the product hierarchy:
  - root `/` should lead with the focused trading graph and arena state
  - the recap/brief belongs underneath the graph as explanation
  - `/brief` can remain as a secondary deep link
  - `/research` remains the deeper tabbed workbench
- Replaced the active brief-first planning docs with focused trading arena docs.

## Files Changed

- `README.md`
- `api/server.py`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/06_INTERVIEW_SYSTEM_DESIGN_NOTES.md`
- `docs/agent_playbook/08_FOCUSED_TRADING_ARENA_POC.md`
- `docs/agent_playbook/09_FOCUSED_TECH_TRADING_EXECUTION_PLAN.md`
- `docs/agent_playbook/session_notes/2026-08-31_status_review_and_site_stabilization.md`
- `docs/agent_playbook/session_notes/2026-08-31_focused_trading_arena_correction.md`

## Design Direction

The first screen should answer:

What are the bots trading in this narrow universe, why are they trading it, how
do those decisions move through risk and the order book, and are they doing
better than `SPY` and `QQQ`?

The brief/recap is still useful, but only as a supporting layer under the graph.
It should explain what changed, what the benchmarks are doing, where the agents
disagree, what evidence matters, and what would change the view.

## Next Recommended Task

Implement Task 0A.5 from `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`:
rebuild root `/` as the focused trading arena. The page should show the graph,
benchmark comparison, latest decisions, orders/fills, positions/PnL, risk state,
and then the recap/brief underneath the graph.

## Open Questions

- Should `/brief` remain as a full-page secondary recap, or become a compact
  shareable permalink to the current arena recap?
- Should `SMH` be added as a visible benchmark before or after the next replay
  pipeline cleanup?
