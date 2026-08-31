import InfoTooltip from "../ui/InfoTooltip";

const BOT_TERMS = [
  ["BearBot", "Pessimistic by design. It looks for downside risk and can open bounded short positions; it never buys."],
  ["AnalystBot", "Evidence-first personality. It prefers limit orders and should only trade on strong support."],
  ["MacroBot", "Connects rates, inflation, yields, and macro shocks to the focused large-cap technology universe."],
];

const SYSTEM_TERMS = [
  ["RAG", "Retrieval augmented generation. The bot searches stored SEC filings and cites chunks instead of relying only on headlines."],
  ["MCP tools", "Internal agent tools for market snapshots, portfolio state, evidence retrieval, risk limits, and risk checks."],
  ["Risk gate", "Deterministic code that validates every proposed order before the C++ engine sees it."],
  ["No-lookahead", "Historical replay retrieval is capped to documents available at the simulated time."],
  ["Evidence-gated", "A trade proposal that requires sufficient retrieved support before it can reach the deterministic risk gate."],
  ["Rejected", "The model proposed a trade, but risk controls blocked it before engine submission."],
  ["Short position", "A simulated position that benefits when price falls. Quantity, order notional, and total exposure remain capped by the same risk gate."],
];

const FAQ = [
  {
    q: "Can visitors trade or start simulations?",
    a: "No. The public site is read-only. Visitors watch the arena, evidence, risk decisions, and results. Operator actions stay behind a private API key.",
  },
  {
    q: "Can agents bypass the risk system?",
    a: "No. Tool preflight can advise an agent, but the scheduler runs the final deterministic risk check before any order reaches the engine.",
  },
  {
    q: "What does the activity timeline show?",
    a: "It shows public-safe breadcrumbs: model call status, RAG retrieval, MCP-style tool calls, risk checks, and order outcomes. It does not show hidden chain-of-thought or secrets.",
  },
  {
    q: "Why do some bots HOLD?",
    a: "A HOLD can be a real decision, a cost-control skip, missing evidence, market-hours gating, malformed model output, or a risk guardrail forcing no trade.",
  },
  {
    q: "Is this real trading?",
    a: "No. This is a simulated market arena with a custom matching engine, synthetic/demo liquidity, and educational model-comparison telemetry.",
  },
];

function TermList({ title, rows }) {
  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <dl className="mt-3 space-y-3">
        {rows.map(([term, definition]) => (
          <div key={term}>
            <dt className="font-mono text-xs font-bold text-slate-900">{term}</dt>
            <dd className="mt-1 text-sm leading-5 text-slate-600">{definition}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function GlossaryFAQ() {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm sm:p-5">
      <div className="max-w-3xl">
        <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
          Reference
          <InfoTooltip label="Why this section exists">
            The dashboard is meant to be readable by recruiters, engineers, and finance-curious visitors without
            requiring them to know trading, RAG, or agent tooling jargon.
          </InfoTooltip>
        </div>
        <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink">How to read the benchmark</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Two model providers run Analyst, Macro, and Bear agents inside one focused market universe. Every proposed
          trade is checked by deterministic rules, matched by the C++ engine, and exposed through an inspectable trail.
        </p>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <TermList title="Bot personalities" rows={BOT_TERMS} />
        <TermList title="System terms" rows={SYSTEM_TERMS} />
      </div>

      <div className="mt-4 rounded-lg border border-border bg-slate-50 p-3">
        <h3 className="px-1 text-sm font-semibold text-ink">Frequently asked questions</h3>
        <div className="mt-2 divide-y divide-border">
          {FAQ.map((item) => (
            <details key={item.q} className="group py-3">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-1 text-sm font-bold text-slate-800">
                <span>{item.q}</span>
                <span className="font-mono text-slate-400 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-2 px-1 text-sm leading-6 text-slate-600">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
