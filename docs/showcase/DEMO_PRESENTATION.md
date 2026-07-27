# Market Simulation Platform Demo Presentation

Use this as the public-facing architecture walkthrough after showing the live
site. It is written to be easy to talk over on screen.

## The 20-Second Story

Market Simulation Platform is an AI trading arena. Claude and OpenAI run the
same five trading personalities, read the same market data and SEC evidence,
pass through the same deterministic risk gate, and trade inside the same C++
limit order book. The app records decisions, fills, evidence, and replay
metrics so the comparison is inspectable instead of hand-wavy.

This is simulated trading only. It does not place real orders.

## Best Live Tour Order

1. Show the homepage and leaderboard.
2. Show a bot detail view and recent decisions.
3. Show the order book so the market mechanics feel real.
4. Show behavior and evaluation so the model comparison feels measured.
5. Open this file and explain how the system is wired together.

## System At A Glance

```mermaid
flowchart LR
    subgraph Inputs
        Prices[Market prices]
        News[News headlines]
        SEC[SEC filings]
    end

    subgraph Intelligence
        Bots[Claude and OpenAI bots]
        RAG[RAG repository]
        MCP[MCP-style tools]
    end

    subgraph Control
        Scheduler[Python scheduler]
        Risk[Deterministic risk gate]
        Engine[C++ order book]
        Portfolio[Portfolio accounting]
    end

    subgraph Product
        DB[Decision and replay storage]
        API[FastAPI and WebSocket API]
        UI[React dashboard]
    end

    SEC --> RAG
    Prices --> Bots
    News --> Bots
    RAG --> Bots
    MCP -. optional tool path .-> Bots
    RAG --> MCP
    Prices --> MCP
    Portfolio --> MCP
    Risk --> MCP
    Bots --> Scheduler
    Scheduler --> Risk
    Risk -->|approved| Engine
    Risk -->|rejected| DB
    Engine --> Portfolio
    Portfolio --> DB
    Bots --> DB
    RAG --> DB
    DB --> API
    Engine --> API
    API --> UI
```

The key point: the models can suggest, but only deterministic Python code can
submit an order to the engine.

<details>
<summary><strong>Expand: One Decision From Prompt To Fill</strong></summary>

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant B as Bot
    participant R as RAG
    participant L as Claude or OpenAI
    participant G as Risk gate
    participant E as C++ engine
    participant D as Database
    participant U as UI

    S->>B: Start decision cycle
    B->>R: Retrieve filing evidence
    R-->>B: Chunk ids and text snippets
    B->>L: Ask for structured BUY, SELL, or HOLD
    L-->>B: JSON decision
    B-->>S: Normalized decision
    S->>G: Enforce deterministic limits
    alt Rejected
        G-->>S: Rejection reason
        S->>D: Persist rejected decision
        S->>U: Publish safe activity event
    else Approved
        G-->>S: Approved
        S->>E: Submit order
        E-->>S: Order id and fills
        S->>D: Persist order, fills, and portfolio snapshot
        S->>U: Publish decision and trade event
    end
```

</details>

<details>
<summary><strong>Expand: MCP Layer, Client To Host To Tools</strong></summary>

```mermaid
flowchart TD
    Client[AnalystBot or local client] --> Host[AgentMcpAdapter]
    Host --> Policy[Auth, filters, approvals, trace metadata]
    Policy --> Server[MarketAgentToolServer]

    Server --> Market[market_snapshot]
    Server --> PortfolioTool[portfolio_snapshot]
    Server --> Evidence[retrieve_evidence]
    Server --> Limits[risk_limits]
    Server --> Preflight[risk_check_order]

    Market --> PriceFeed[Price feed]
    PortfolioTool --> Portfolios[Bot portfolios]
    Evidence --> Repo[RagRepository]
    Repo --> FilingChunks[SEC filing chunks]
    Limits --> SharedLimits[Shared RiskLimits]
    Preflight --> RiskCode[Deterministic risk code]

    Host --> Traces[Safe activity traces]
    Host --> Audit[Protected audit rows]
```

How to explain it:

- The client is either AnalystBot in tool mode or a local MCP client.
- The host is the adapter plus the in-process tool server.
- The tools do not bypass system rules.
- `retrieve_evidence` reaches into the same RAG store used by the direct prompt
  path.
- `risk_check_order` is only a preflight. The scheduler repeats the real check
  before execution.

</details>

<details>
<summary><strong>Expand: RAG Pipeline</strong></summary>

```mermaid
flowchart LR
    Poller[SEC poller] --> Detect[Find new filings]
    Detect --> Fetch[Fetch 10-K, 10-Q, and 8-K HTML]
    Fetch --> Clean[Normalize text]
    Clean --> Dedupe[Deduplicate by accession, URL, then hash]
    Dedupe --> Chunk[Create bounded chunks]
    Chunk --> Embed[Generate embeddings]
    Embed --> Store[Store documents and chunks]
    Store --> Retrieve[Vector search with keyword fallback]
    Retrieve --> Prompt[Send evidence into bot prompt]
    Prompt --> Persist[Persist cited chunk ids and source URLs]
```

Why it matters:

- The evidence is dateable, so replay can enforce no-lookahead behavior.
- The model cites chunk ids instead of inventing sources.
- Reviewers can open the exact filing snippet behind a decision.

</details>

<details>
<summary><strong>Expand: Execution And Passive Fill Attribution</strong></summary>

```mermaid
flowchart TD
    Resting[Resting limit order] --> Book[C++ order book]
    Incoming[Later incoming order] --> Book
    Book --> Trade[Trade has both buy and sell order ids]
    Trade --> IncomingFill[Immediate fill for incoming order]
    Trade --> PassiveFill[Queued fill for resting order]
    IncomingFill --> Ledger[Execution ledger and portfolio updates]
    PassiveFill --> Ledger
```

Why it matters:

- It keeps both counterparties correct.
- It keeps portfolio state, replay results, and the UI in sync.
- It is one of the places where the native engine and Python orchestration have
  to agree exactly.

</details>

## What This Demonstrates

- Market structure: price-time priority, limit and market orders, fills,
  liquidity, and PnL.
- AI systems design: structured model output, evidence retrieval, tool access,
  and deterministic safety boundaries.
- Full-stack engineering: C++, Python, FastAPI, SQLAlchemy, React, Docker, and
  deployment packaging.
- Evaluation discipline: replay, no-lookahead RAG, citations, risk rejection
  rates, and provider comparisons on the same inputs.

## Good Closing Line

The interesting part is not just "an LLM made a trade." The interesting part is
that every step around the model is inspectable: what it saw, what evidence it
used, what the risk gate allowed, how the engine filled it, and how the result
was measured.

## Related Docs

- [Repository README](../../README.md)
- [Recruiter Overview](RECRUITER_OVERVIEW.md)
- [MCP And Agent Integration](../architecture/MCP.md)
- [Deployment Runbook](../operations/DEPLOYMENT.md)
- [Release And Smoke Checklist](../operations/RELEASE.md)
