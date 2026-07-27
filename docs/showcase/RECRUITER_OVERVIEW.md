# Recruiter Overview

Use this when presenting the public read-only showcase. Keep the framing simple:
this is not a real trading product; it is an AI systems, market-structure, and
full-stack engineering demo.

## 60-Second Pitch

AI Trading Arena compares Claude and OpenAI as trading agents. Ten bots share the
same market, news, RAG evidence, and deterministic risk rules. The agents emit
structured decisions, the scheduler validates each order, a C++ limit order book
simulates fills, and the dashboard shows the public-safe trail: evidence,
rationales, risk rejections, fills, PnL, replay metrics, and retrieval quality.

## Best Live Tour

1. Open `/` and show the Claude vs OpenAI average return chart.
2. Point out the app is public read-only: visitors can inspect, not control.
3. Show the live decision tape: proposed action, ticker, quantity, outcome, and
   concise public rationale.
4. Show Agent Telemetry: model calls, RAG/MCP-style tool calls, risk checks, and
   execution outcomes without hidden chain-of-thought or secrets.
5. Open the FAQ/glossary and explain DegenBot, RAG, MCP tools, risk gate, and
   no-lookahead in plain English.
6. Open `/bots`, select a bot, and show its portfolio chart, positions,
   decision history, evidence counts, and model provider label.
7. Open `/book` and connect agent decisions to bid/ask depth and fills.
8. Open `/behavior` to compare action mix, confidence, citations, risk
   rejections, fills, and portfolio value.
9. Open `/eval` to show citation/speculative/unsupported rates, replay runs,
   model comparisons, and JSON/CSV exports.
10. Open `/retrieval` to show the RAG document library, retrieval benchmark, and
    no-lookahead evidence story.
11. Open `/config` to show public-safe model, risk, data, and budget settings.

## Strong Technical Points

- C++17 matching engine with Python adapter and Docker native-engine smoke check.
- Scheduler-level risk gate is the final authority before engine submission.
- Structured LLM output is sanitized before it affects trading logic.
- Analyst and Macro bots require evidence before trading; DegenBot is explicitly
  labeled speculative.
- Historical replay retrieval is timestamp-capped to prevent future evidence.
- Public telemetry avoids hidden chain-of-thought, raw prompts, secrets, and raw
  tool arguments.
- Render Blueprint defines API, static frontend, and Postgres.
- App-side model spend caps, prompt trimming, caching, and route-level frontend
  code splitting keep the showcase cost-conscious.
- The Render free-plan demo can sleep when idle. The API wakes on request, but
  true continuous unattended simulation requires an always-on service or worker.

## What To Say If Asked About Production

The repository is ready for a public read-only showcase once host secrets are
entered, the native engine passes in deployment, and deployed smoke checks pass.
It should not be described as a multi-user trading product. Before that, it
would need production identity, backups, monitoring/alerting, provider-side
billing caps, larger audited datasets, and an open-order rehydration strategy.

## What Not To Claim

- Do not claim real-money trading.
- Do not claim financial advice or market prediction quality.
- Do not show hidden chain-of-thought; show public rationales and evidence.
- Do not expose `ARENA_API_KEY`, provider keys, database URLs, or host logs with
  secrets.

For the visual architecture walkthrough, use
[`DEMO_PRESENTATION.md`](DEMO_PRESENTATION.md).
