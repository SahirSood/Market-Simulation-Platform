# Agent Playbook Created

Date: 2026-08-18

Agent: Codex

Task: Create detailed continuation documents for future agents and for
architecture/system-design interview explanation.

## Summary

Created a dedicated agent playbook under `docs/agent_playbook`.

The folder explains:

- current system architecture
- current project state
- how live trading flows through the system
- how replay works
- why live and replay standings must stay separate
- how to build a six-month replay dataset
- how to use that replay data for ML evaluation
- what remains to build
- how future agents should update project state after tasks
- how the owner can explain the system in interviews

## Files Changed

- `docs/README.md`
- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/01_ARCHITECTURE_AND_SYSTEM_DESIGN.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/05_AGENT_UPDATE_PROTOCOL.md`
- `docs/agent_playbook/06_INTERVIEW_SYSTEM_DESIGN_NOTES.md`
- `docs/agent_playbook/templates/TASK_NOTE_TEMPLATE.md`
- `docs/agent_playbook/session_notes/2026-08-18_agent_playbook_created.md`

## Commands Run

```powershell
Get-ChildItem docs -Recurse -File | Select-Object -ExpandProperty FullName
Get-ChildItem data\replay_events -File | Select-Object -ExpandProperty Name
rg -n "replay|outcome|evaluation|leaderboard|benchmark|SPY|S&P|dataset|ML|machine" README.md docs simulator scripts api frontend/src -g "*.md" -g "*.py" -g "*.jsx" -g "*.js"
New-Item -ItemType Directory -Force docs\agent_playbook, docs\agent_playbook\templates
New-Item -ItemType Directory -Force docs\agent_playbook\session_notes
```

## Results

- Documentation folder created.
- Existing docs index now links to the agent playbook.
- The next major task is explicitly documented as the six-month historical replay
  event generator.
- No backend/frontend code was changed in this session.
- No tests were required because this was documentation-only work.

## Design Decisions

- Created a separate `docs/agent_playbook` folder instead of putting long
  handoff notes into the main README.
- Kept `AGENT_STATE.md` mutable and task-focused so future agents can update it.
- Kept architecture and interview notes separate so the owner has an explanation
  file that is easy to rehearse.
- Documented that replay/backtest standings should not silently overwrite live
  standings.
- Documented a staged six-month replay plan to control token cost.

## Risks Or Caveats

- The historical replay event generator is not implemented yet.
- Large replay runs can spend model-provider tokens quickly.
- Historical news coverage may require a separate data source or a staged
  price-first approach.
- SPY benchmark scoring needs implementation before six-month standings are
  complete.

## Next Recommended Task

Build `scripts/build_historical_replay_events.py` for a one-month daily pilot.

## Open Questions

- Should generated historical events be price-only first, or should historical
  news enrichment be attempted immediately?
- Should replay standings live inside the existing Eval page first, or should
  they get a dedicated route/page?
- Should the initial six-agent replay set be exactly analyst/bear/macro across
  Claude and OpenAI?

