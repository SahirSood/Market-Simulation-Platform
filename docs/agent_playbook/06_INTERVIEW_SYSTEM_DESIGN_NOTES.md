# Interview System Design Notes

This document is for explaining the project to recruiters, engineers, and
capital-markets interviewers.

## One-Sentence Pitch

I built an agentic capital-markets simulation platform where LLM agents use
market data, RAG evidence, replay, and MCP-style tools to produce structured
trade proposals, pass simulated orders through deterministic risk controls and a
C++ order book, and generate ML-ready outcome labels.

## Thirty-Second Pitch

This is not just a chatbot that says "buy" or "sell." The LLM is one part of a
larger trading system. Core agents produce structured trade proposals, while
deterministic services handle parsing, guardrails, risk checks, C++ order-book
execution, portfolio accounting, logging, replay, and evaluation. The next
product surface is a focused AI infrastructure trading arena: one narrow
universe, visible simulated trades, benchmark comparison, and a recap that
explains why the agents acted.

## Two-Minute Architecture Explanation

The platform has a FastAPI backend, a React frontend, a Python simulator layer,
a C++ matching engine boundary, a RAG evidence store, and evaluation/replay
modules.

At startup, FastAPI wires together the price feed, news feed, RAG repository,
embedding service, engine adapter, risk limits, bot instances, schedulers, replay
store, and reasoning log. The live scheduler runs bots on staggered intervals
and respects market-hours and cost-budget gates.

Each bot inherits from a shared `BaseBot`. The bot builds market context, adds
RAG evidence, calls Claude or OpenAI, and expects a structured JSON decision. The
parser sanitizes the response into an `OrderDecision`. Then the scheduler sends
non-HOLD decisions through deterministic risk checks. Only approved orders reach
the engine adapter. Fills update the bot portfolio and everything is persisted
to the reasoning log.

The evaluation side turns raw decisions into metrics. Live decisions get future
outcome labels at horizons like 1 hour, 6 hours, 1 day, and 7 days. Replay runs
feed historical/scenario events into the same agents and compare providers or
prompts using the same input fingerprint. That gives me controlled, repeatable
evaluations instead of anecdotal demos.

The current product phase is narrowing the completed trading/replay/evaluation
work into one focused arena. I generated historical daily event streams,
replayed the core agents over that period, exported an ML-ready dataset, and now
use that evidence to improve an AI infrastructure / large-cap technology
trading simulation instead of spreading attention across every market at once.

## Explain It Like I Am 12

Imagine each trading bot is a student in a class.

Every day, each student gets the same worksheet:

- today's prices
- market news
- company evidence
- their current pretend money

Each student writes down:

- buy
- sell
- hold
- what ticker
- how many shares
- why

But the student is not allowed to run straight to the stock market. First, a
strict teacher checks the answer:

- Is the ticker allowed?
- Is the trade too big?
- Does the student have enough cash?
- Would this create too much risk?

Only then can the trade go to the pretend stock exchange.

After that, we save everything in a notebook. Later, we check:

- Was the student right?
- Did they make pretend money?
- Did they beat SPY?
- Did the strict teacher block a bad trade or a good trade?

Replay is like giving the students old worksheets from the last six months and
asking, "What would you have done back then?"

## Key Design Decision: LLM As Proposal Generator

The most important design decision:

```text
The LLM does not execute trades. It proposes decisions.
```

Why:

- LLM output can be malformed.
- LLM reasoning can be overconfident.
- LLMs can hallucinate.
- Financial systems need deterministic controls.
- Risk logic must be testable and auditable.

The LLM is useful for interpretation. The system is responsible for control.

## Key Design Decision: Structured JSON Contract

Every model response must become an `OrderDecision`.

Why:

- risk checks need action/ticker/quantity
- execution needs order details
- logs need stable fields
- replay needs comparable rows
- ML export needs columns
- UI needs consistent data

Without structured output, everything downstream becomes fragile.

## Key Design Decision: Deterministic Risk Layer

Risk checks are normal code, not an LLM prompt.

This is important in finance because you need predictable behavior:

- max order size
- max notional
- position limits
- cash checks
- short-selling flag
- tradable universe

Interview phrasing:

> I intentionally separated probabilistic decision-making from deterministic
> risk enforcement. The model can recommend a trade, but only code can approve
> it.

## Key Design Decision: Replay Instead Of Waiting

The system needs historical evidence, but waiting six months for live decisions
is slow.

Replay solves this:

```text
Use historical inputs -> run current agents -> score decisions against what
happened next.
```

Why this is strong:

- same agents
- same risk layer
- same parser
- same model providers
- same evaluation metrics
- identical inputs across providers
- no-lookahead can be enforced

This makes comparisons fair.

## Key Design Decision: Separate Live And Replay Standings

Live standings answer:

```text
What happened while the system actually ran live?
```

Replay standings answer:

```text
What would the current system have done on past inputs?
```

They are both valuable, but they should not be mixed silently.

Interview phrasing:

> I treat replay as a backtest/evaluation track, not as live production
> performance. That keeps the metrics honest.

## Key Design Decision: RAG For Evidence

RAG gives agents external evidence.

Why:

- models do not know all current filings/news
- evidence ids create auditability
- citations let us measure unsupported trades
- no-lookahead RAG makes replay more defensible

Interview phrasing:

> RAG is not just there to make the prompt better. It creates a measurable
> evidence trail so we can ask whether evidence-backed trades outperform
> unsupported trades.

## Key Design Decision: MCP/Tools

The tool layer exposes market snapshots, portfolio snapshots, evidence
retrieval, and risk checks through a reusable interface.

Why:

- agents can use tools instead of only static prompts
- tools are permissioned
- tool calls are traceable
- the same tool server can be exposed in-process or over HTTP

Interview phrasing:

> I designed the tools as transport-agnostic services, then wrapped them with an
> MCP-style adapter. That keeps business logic separate from protocol concerns.

## Key Design Decision: Store Raw Facts, Derive Metrics Later

The platform stores raw decisions, orders, fills, evidence ids, event payloads,
and model metadata.

Then evaluation computes:

- win rate
- PnL
- evidence quality
- risk rejection rates
- replay directional accuracy
- cost-adjusted results

Why:

- metrics can improve without rerunning expensive LLM calls
- raw audit trail remains intact
- ML datasets can be versioned

## Best Interview Themes

Use these phrases:

- agentic AI system
- deterministic guardrails around LLMs
- RAG-backed decision support
- MCP-style tool integration
- historical replay and no-lookahead evaluation
- model/provider comparison
- prompt-version experiment tracking
- auditability and observability
- cost-aware AI operations
- ML-ready decision/outcome labels
- risk-controlled simulation
- benchmark-relative evaluation

## What Makes It Capital-Markets Relevant

Capital markets systems care about:

- market data
- risk limits
- order management
- execution
- audit logs
- backtesting
- benchmark comparison
- PnL
- drawdowns
- model evaluation
- cost and latency
- compliance-style traceability

This project touches all of those in prototype form.

## How To Explain The Replay-Backed Arena

Use this:

> I use historical replay to evaluate the trading arena without waiting months
> for live decisions. I generate replay events from historical market data and
> no-lookahead news/evidence, run the same core agents over those events, and
> score their simulated trades against future prices and benchmarks such as SPY
> and QQQ. The user sees bot trades, risk checks, order-book behavior, and a
> recap explaining why the agents acted.

## How To Explain The ML Plan

Use this:

> I am not jumping straight to reinforcement learning. First I want a clean
> supervised dataset. Each row is one agent decision with features available at
> decision time and labels from future outcomes. I can train interpretable
> baselines like logistic regression and tree models to identify when an agent's
> view is likely to be useful, risky, or benchmark-lagging. The first use is
> trust and evaluation inside the focused trading arena. Later it can become a
> meta-router that decides which agent to trust in each market regime.

## Likely Interview Questions And Answers

### Why not let the LLM directly trade?

Because LLM output is probabilistic. In a financial system, execution must be
controlled by deterministic checks. The LLM proposes, but risk and execution
services decide what is allowed.

### Why use replay?

Live data collection takes too long. Replay lets us evaluate current agents on
past scenarios with identical inputs, which makes provider and prompt comparison
fair.

### How do you prevent lookahead bias?

Replay events have timestamps. Price/news/RAG context must be available at or
before the event timestamp. Labels can look into the future, but prompts cannot.

### Why compare to SPY?

Absolute PnL is not enough. If the market was up 10% and the bots were up 2%,
they underperformed. SPY gives a simple tradable benchmark.

### Why use RAG?

RAG gives the model evidence and gives the system an audit trail. It also lets
us evaluate citation quality and unsupported trades.

### Why use MCP?

MCP-style tools make agent capabilities explicit, permissioned, and traceable.
They also make tool logic reusable across local agents, HTTP transport, and
future integrations.

### What is the biggest current limitation?

The platform is technically broad, so the next challenge is product focus. The
first useful surface should be a narrowed trading arena for one sector, with
benchmarks, replay, RAG evidence, and ML evaluation supporting the user-visible
trading loop.

### What would you improve next?

I would rebuild the root UI around the focused trading arena, starting with AI
infrastructure / large-cap technology. Then I would place the recap under the
main graph, improve HOLD opportunity labels, and add replay cost estimates so we
can explain when agents were right, wrong, too cautious, or not worth the cost.

### Is this production trading ready?

No. It is a research/simulation platform. Production trading would require
stronger market data, order management, compliance controls, monitoring, broker
integration, short borrow/margin logic, and much deeper testing.

That answer is good. It is honest and mature.
