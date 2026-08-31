# Session Note: Narrow Tech Sector Decision Brief Plan

Date: 2026-08-25

Status: Superseded on 2026-08-31 by
`2026-08-31_focused_trading_arena_correction.md`. This note remains useful
history for the narrowed universe and benchmarks, but the active product is now
the focused trading arena with the recap/brief underneath the graph.

## Summary

Updated the project plan after re-reading the current playbook, roadmap, and
decision-brief pivot docs.

The clarification is that the project should not keep expanding the broad
simulation platform until the first user-facing workflow clearly answers:

```text
So what?
```

The next product goal is a narrow, useful tech-sector investment brief for AI
infrastructure / large-cap technology.

## What Changed

- Added `docs/agent_playbook/09_TECH_SECTOR_DECISION_BRIEF_EXECUTION_PLAN.md`.
- Updated the playbook read order to include the new execution plan.
- Updated the current north star to emphasize that the brief must show the
  answer before the machinery.
- Expanded Phase 0A in the roadmap with a scope rule and a completed planning
  task.
- Tightened the decision-brief API acceptance criteria.
- Tightened the Investment Brief frontend acceptance criteria.
- Added follow-up tasks for making Evaluation support the brief and for adding
  an explicit caveat/honesty layer.
- Updated `AGENT_STATE.md` with the latest planning clarification and next
  recommended task.
- Updated runtime defaults so the system actually trades the focused tech
  universe instead of the older broad demo basket.
- Added separate benchmark ticker configuration for `SPY` and `QQQ`.
- Updated bot prompt context so tradable tickers and benchmark tickers are
  shown separately.
- Disabled automatic research-driven expansion of the tradable universe by
  default.
- Updated tests that assumed `AAPL` was a default tradable ticker.
- Added the deterministic read-only decision brief endpoint:
  `GET /evaluation/decision-brief`.
- Added the new Investment Brief frontend page and made it the root product
  surface.
- Simplified the site navigation to `Brief` and `Research`.
- Added `/research` as a tabbed workbench for Evidence, Evaluation, Bots, Order
  Book, Behavior, and Config.
- Redirected old top-level dashboard routes into matching research tabs.

## Files Changed

- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/08_CORE_AGENT_DECISION_BRIEF.md`
- `docs/agent_playbook/09_TECH_SECTOR_DECISION_BRIEF_EXECUTION_PLAN.md`
- `docs/agent_playbook/session_notes/2026-08-25_narrow_tech_sector_decision_brief_plan.md`
- `.env.example`
- `.env.production.example`
- `api/routers/config.py`
- `api/routers/evaluation.py`
- `api/tests/test_evaluation_router.py`
- `frontend/src/App.jsx`
- `frontend/src/api/endpoints.js`
- `frontend/src/components/layout/Navbar.jsx`
- `frontend/src/pages/BriefPage.jsx`
- `frontend/src/pages/ResearchHubPage.jsx`
- `frontend/src/pages/ConfigPage.jsx`
- `simulator/base_bot.py`
- `simulator/config.py`
- `simulator/model_config.py`
- `simulator/tests/test_agent_tools.py`
- `simulator/tests/test_llm_cost_controls.py`
- `simulator/tests/test_replay.py`
- `simulator/tests/test_research.py`
- `simulator/tests/test_risk.py`
- `simulator/tests/test_scheduler.py`

## Decisions

- First POC scope remains AI infrastructure / large-cap technology.
- First ticker universe: `NVDA`, `AMD`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`,
  `TSLA`.
- First benchmarks: `SPY`, `QQQ`.
- `SMH` is deferred until it is added cleanly to price/replay support.
- The first decision frame is investor-facing: add, wait, reduce, or research
  more.
- The first page should be an Investment Brief route, likely `/brief`, and the
  existing arena/evaluation views should become supporting surfaces.
- The live default tradable universe should be the seven tech names only.
- `SPY` and `QQQ` should be benchmark context by default, not tradable symbols.
- Research can still ingest evidence, but it should not quietly expand what the
  bots are allowed to trade unless explicitly configured.
- The first product surface is the brief, not the arena/evaluation dashboard.
- The deeper platform surfaces should live under a single research/workbench
  route until there is a reason to promote one again.

## Verification

Commands run:

```powershell
python -m py_compile simulator\config.py simulator\base_bot.py simulator\model_config.py api\routers\config.py
pytest -q simulator\tests\test_risk.py simulator\tests\test_llm_cost_controls.py simulator\tests\test_research.py api\tests\test_server_env.py
pytest -q simulator\tests\test_agent_tools.py simulator\tests\test_replay.py simulator\tests\test_scheduler.py
pytest -q api\tests\test_evaluation_router.py::test_get_decision_brief_returns_focused_payload api\tests\test_evaluation_router.py::test_get_decision_brief_rejects_outside_universe_ticker
cd frontend; npm run build
pytest -q
```

Results:

- Focused config/context/risk/research/API tests: `41 passed`.
- Replay/tool/scheduler slice: `24 passed`.
- Decision brief API focused tests: `2 passed`.
- Frontend production build passed.
- Full backend suite: `219 passed, 1 skipped`.

## Next Recommended Task

Run the focused live trading loop and inspect whether Analyst/Macro/Bear are
producing useful decisions for the seven-name tech universe. Then tune prompts,
evidence retrieval, and replay evaluation for this exact basket.

## Open Questions

- Should `/brief` become the root route, or should the root route redirect to
  `/brief` while keeping the old arena at `/arena`?
- Should the initial deterministic recommendation be purely rule-based, or
  should it include a cached/latest stored agent consensus when available?
- Should the first UI show provider differences immediately, or hide them under
  each Analyst/Macro/Bear perspective until the user drills in?
