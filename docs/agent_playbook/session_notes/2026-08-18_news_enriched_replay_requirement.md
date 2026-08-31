# News-Enriched Replay Requirement Added

Date: 2026-08-18

Agent: Codex

Task: Update the agent playbook to clarify that serious replay and ML work must
use news/event context, not price-only replay.

## Summary

Updated the plans to reflect that the current bots trade from market/news/RAG
context. A replay dataset that only contains historical prices is useful for
testing plumbing, but it is not representative enough for ML conclusions about
agent quality.

The docs now say:

- price-only replay is allowed only as a smoke test
- the first real one-month pilot should be news-enriched
- the six-month replay dataset should be news-enriched
- generated replay events should include `trending_headlines`,
  `recent_headlines`, and `ticker_headlines`
- historical headlines/events must obey no-lookahead
- synthetic price-derived summaries must be clearly marked

## Files Changed

- `docs/agent_playbook/README.md`
- `docs/agent_playbook/AGENT_STATE.md`
- `docs/agent_playbook/02_SIX_MONTH_REPLAY_DATA_PROGRAM.md`
- `docs/agent_playbook/03_ML_EVALUATION_AND_RESEARCH_PLAN.md`
- `docs/agent_playbook/04_ROADMAP_AND_BACKLOG.md`
- `docs/agent_playbook/05_AGENT_UPDATE_PROTOCOL.md`
- `docs/agent_playbook/session_notes/2026-08-18_news_enriched_replay_requirement.md`

## Commands Run

```powershell
$i=0; Get-Content docs\agent_playbook\02_SIX_MONTH_REPLAY_DATA_PROGRAM.md | ForEach-Object { ... }
$i=0; Get-Content docs\agent_playbook\AGENT_STATE.md | ForEach-Object { ... }
$i=0; Get-Content docs\agent_playbook\04_ROADMAP_AND_BACKLOG.md | ForEach-Object { ... }
```

## Results

- Plans now prioritize historical news/event context before the serious
  six-month replay.
- The backlog now includes a first task to choose the historical news/event
  context source.
- ML plan now includes news context features and quality flags.

## Design Decisions

- Kept price-only replay as an explicit smoke-test path because it is useful for
  validating schema, generation, loading, and scoring cheaply.
- Marked news-enriched replay as required for decision-grade ML because it
  matches how the current bots receive context.
- Included synthetic market summaries as a fallback, but only with clear
  metadata and no-lookahead constraints.

## Risks Or Caveats

- A low-cost historical news provider still needs to be chosen.
- Historical news availability may be incomplete.
- Synthetic summaries can create bias if written with hindsight, so they must be
  generated only from data known at the event timestamp.

## Next Recommended Task

Choose the minimum viable historical news/event context source, then implement
`scripts/build_historical_replay_events.py` with a `--news-mode` option.

## Open Questions

- Which historical news source is affordable enough for this project?
- What minimum headline coverage should a replay event need before being called
  ML-grade?
- Should calendar events and SEC/RAG events count as "news" for the first pilot?

