                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             # Agent Update Protocol

This file tells future agents how to work on the project without losing context.

## Prime Directive

Before ending any meaningful work session, update the project memory.

At minimum:

1. Update `AGENT_STATE.md`.
2. Update any relevant checklist in `04_ROADMAP_AND_BACKLOG.md`.
3. Add a session note using `templates/TASK_NOTE_TEMPLATE.md`.
4. Record tests/builds run.
5. Record what should happen next.

## Why This Matters

The user wants this project to continue across sessions and agents. The biggest
risk is not only a code bug. The biggest risk is context loss:

- forgetting what was already built
- repeating old explanations
- running expensive replay twice
- mixing live and replay standings
- losing the reason behind a design decision
- leaving the next agent unsure where to begin

This protocol prevents that.

## Startup Checklist For Future Agents

Before editing code:

1. Read `docs/agent_playbook/README.md`.
2. Read `docs/agent_playbook/AGENT_STATE.md`.
3. Read the relevant plan file for the task.
4. Run:

```powershell
git status --short
```

5. Inspect the files you plan to edit.
6. Check whether the backend/frontend are running if the task depends on them.
7. If replay/model calls are involved, estimate cost before running.

## Work Session Rules

### Rule 1: Do Not Hide Cost

Replay can call model providers many times.

Before running a large replay:

- compute expected call count
- explain expected scale
- prefer a one-month pilot
- use `--no-orders` first
- use low effort when appropriate
- write a report

### Rule 2: Keep Replay And Live Data Separate

Do not update live standings with replay data unless the UI/API explicitly labels
the result as replay/backtest.

Correct:

- "Six-Month Replay Standings"
- "Backtest Leaderboard"
- "Replay Intent PnL"

Incorrect:

- pretending the bot actually traded live for six months
- silently merging replay PnL into live leaderboard

### Rule 3: Maintain No-Lookahead

Replay inputs must not contain future information.

For every generated event:

- feature timestamp must be at or before event timestamp
- headline `published_at` must be at or before event timestamp
- RAG documents must be published at or before event timestamp
- labels may use future prices, but labels must not be in the prompt

### Rule 3A: Replay Must Match The Live Decision Context

The current bots trade from news and evidence, not prices alone.

For decision-grade replay:

- include broad market headlines
- include recent headlines
- include ticker-specific headlines
- include RAG/SEC evidence where available
- include source/timestamp metadata
- mark synthetic price-derived summaries as synthetic

Price-only replay is acceptable for plumbing tests, but it should be labeled as
smoke-test data and should not drive ML conclusions or agent pruning.

### Rule 4: Preserve Raw Data

Do not mutate raw decision records to support an experiment.

Instead:

- compute derived metrics at query time
- export versioned datasets
- add new tables only when needed

### Rule 5: Prefer Small Pilots

For any major data job:

1. dry run
2. tiny fixture
3. one-month pilot
4. full six-month run

### Rule 6: Validate Fixes With Replay

After a material fix, do not rely only on intuition.

Run a replay regression suite when changing:

- prompts
- parser behavior
- risk logic
- replay scoring
- RAG evidence guardrails
- ML feature engineering
- model/provider configuration

The replay report should say whether the change improved, regressed, or needs
more data.

### Rule 7: Run A Recurring Live-Data Review

The system should learn from real data over time.

Default cadence:

- weekly live-data report
- data-threshold fallback if weekly sample is too small
- monthly deeper agent/prompt review

Suggested threshold:

```text
50 new decisions or 50 new outcome labels
```

If there are fewer rows, the report should still be allowed, but it must be
marked "monitoring only" and should not drive major agent pruning decisions.

### Rule 8: Refresh ML After Meaningful Changes

Refresh ML datasets and reports when:

- six-month replay data changes
- enough new live outcome labels exist
- prompt version changes
- parser/risk/evidence logic changes
- benchmark scoring changes

Do not retrain or present model results as final when there are too few new
labels.

### Rule 9: Log Design Decisions

If a task makes an architectural choice, record:

- what changed
- why
- tradeoffs
- rejected alternatives
- future implications

## Required Handoff Update Format

Append to `AGENT_STATE.md` under `Update Log`:

```markdown
### YYYY-MM-DD

Summary:

- ...

Files changed:

- ...

Commands run:

- ...

Results:

- ...

Next recommended task:

- ...

Open questions:

- ...
```

## Task Note Template

Use:

- `docs/agent_playbook/templates/TASK_NOTE_TEMPLATE.md`

Recommended location for task notes:

```text
docs/agent_playbook/session_notes/
```

If that folder does not exist yet, create it when first needed.

Filename format:

```text
YYYY-MM-DD_short_task_name.md
```

Examples:

```text
2026-08-18_agent_playbook_created.md
2026-08-19_historical_event_builder.md
2026-08-20_one_month_replay_pilot.md
```

## Definition Of Done For Code Tasks

A code task is done when:

- implementation is complete
- tests are added or consciously not needed
- relevant tests pass
- frontend build passes if frontend changed
- docs/status are updated
- next task is clear

## Definition Of Done For Data Tasks

A data task is done when:

- generated artifact exists
- quality report exists
- source and date window are recorded
- secrets are not present
- replay compatibility is verified
- cost/report metadata is saved if model calls ran
- downstream next step is recorded

## Definition Of Done For Replay Tasks

A replay task is done when:

- run command is recorded
- provider set is recorded
- bot set is recorded
- model/prompt version is recorded
- execution mode is recorded
- run IDs are recorded
- input fingerprint is recorded
- report artifact is written
- comparison endpoint works or failure is documented
- costs are recorded or estimated

## Definition Of Done For ML Tasks

An ML task is done when:

- dataset version is recorded
- feature dictionary is written
- target label is defined
- leakage checks are documented
- split method is time-based unless explicitly exploratory
- metrics are saved
- interpretation is written
- limitations are written

## Things Future Agents Should Not Do

Do not:

- expose `.env` secrets in generated reports
- commit raw API keys
- run unbounded replay loops
- enable scheduled replay at high frequency without approval
- use future data in replay prompts
- claim replay PnL is live PnL
- skip tests after touching evaluation/risk/replay/parser code
- delete user changes
- refactor unrelated modules just because they look imperfect

## Quick Handoff Checklist

Before final response:

- [ ] What did I change?
- [ ] Why did I change it?
- [ ] What files changed?
- [ ] What tests/builds ran?
- [ ] What is still unfinished?
- [ ] What should the next agent do first?
- [ ] Did I update `AGENT_STATE.md`?
- [ ] Did I update backlog statuses?
- [ ] If this was a fix/prompt/risk/parser change, did I run or schedule replay
      regression?
- [ ] If new live data arrived, did I update or schedule the weekly/data-threshold
      evaluation report?
