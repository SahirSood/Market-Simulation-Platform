# Session Note: Core Agent Decision Brief Pivot

Date: 2026-08-20

Status: Superseded on 2026-08-31 by
`2026-08-31_focused_trading_arena_correction.md`. This note remains useful
history for why the scope narrowed, but the active product is now the focused
trading arena with the recap/brief underneath the graph.

## Summary

Pivoted the project direction from a broad trading-arena surface toward a
focused investment decision brief POC for AI infrastructure / large-cap
technology.

The existing code is preserved. DegenBot and ContrarianBot are parked from the
serious live startup list by comments, not deleted.

## What Changed

- Added `docs/agent_playbook/08_CORE_AGENT_DECISION_BRIEF.md`.
- Updated the playbook README read order and north star.
- Updated the mutable agent state with the new POC direction.
- Added Phase 0A to the roadmap for the investment decision brief.
- Reframed the ML plan around trust/evaluation for the brief.
- Updated interview notes to explain the project as a replay-backed decision
  platform.
- Updated the public README to describe six core live perspectives.
- Commented DegenBot and ContrarianBot out of:
  - `api/server.py`
  - `simulator/main.py`

## Files Changed

- `README.md`
- `api/server.py`
- `simulator/main.py`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/01_ARCHITECTURE_AND_SYSTEM_DESIGN.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/06_INTERVIEW_SYSTEM_DESIGN_NOTES.md`
- `docs/agent_playbook/08_CORE_AGENT_DECISION_BRIEF.md`
- `docs/agent_playbook/session_notes/2026-08-20_core_agent_decision_brief_pivot.md`

## Commands Run

```powershell
python -m py_compile api\server.py simulator\main.py
pytest -q simulator/tests/test_bots.py simulator/tests/test_replay_datasets.py api/tests/test_server_env.py
pytest -q simulator/tests/test_replay.py simulator/tests/test_replay_datasets.py api/tests/test_smoke_deployment.py
```

## Results

- Python compile passed for the changed startup files.
- Focused bot/replay/server-env tests: `14 passed`.
- Replay/server smoke slice: `13 passed`.

## Design Decisions

- The project should now lead with a practical investment brief instead of a
  broad day-trading leaderboard.
- AnalystBot, MacroBot, and BearBot form the serious core agent debate.
- DegenBot and ContrarianBot remain implemented for sandbox and replay because
  they still demonstrate architectural extensibility.
- ML remains an evaluation/trust layer until labels, costs, and validation are
  stronger.

## Risks Or Caveats

- Full `pytest -q` was not rerun in this session.
- Frontend build was not rerun because no frontend source code changed.
- Existing unrelated uncommitted work remains in the repository.

## Next Recommended Task

- Build the decision-brief API/read model from existing replay, RAG, and
  evaluation artifacts, then add the focused Investment Brief frontend page.

## Open Questions

- Should the first sector universe be exactly `NVDA`, `AMD`, `AVGO`, `AMZN`,
  `MSFT`, `GOOGL`, and `TSLA`?
- Should `QQQ` be the primary benchmark until `SMH` is added to the replay and
  price pipeline?
