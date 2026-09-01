import InfoTooltip from "../ui/InfoTooltip";

function percent(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  const number = Number(value) * 100;
  return `${number.toFixed(digits)}%`;
}

function signedPercent(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  const number = Number(value) * 100;
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}%`;
}

function number(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function providerLabel(provider) {
  return provider === "claude" ? "Claude" : "OpenAI";
}

function topHoldCause(counts = {}) {
  const [cause, count] = Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]))[0] || [];
  if (!cause) return "No hold pattern yet";
  return `${cause.replaceAll("_", " ")} (${count})`;
}

function Metric({ label, value, detail, tone = "text-ink" }) {
  return (
    <div className="min-w-0 rounded-md border border-border bg-slate-50 px-3 py-3">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className={`mt-1 truncate text-lg font-semibold tabular-nums ${tone}`}>{value}</div>
      <div className="mt-0.5 truncate text-xs text-slate-500">{detail}</div>
    </div>
  );
}

function BenchmarkCard({ ticker, row }) {
  const excess = row?.avg_excess_return;
  return (
    <div className="rounded-md border border-border bg-white px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-sm font-semibold text-ink">{ticker}</span>
        <span className={`font-mono text-xs font-semibold ${Number(excess) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
          {signedPercent(excess)} excess
        </span>
      </div>
      <div className="mt-2 text-sm text-slate-700">
        Benchmark {signedPercent(row?.avg_benchmark_return)} · agents beat it {percent(row?.beat_rate, 1)} of comparisons
      </div>
    </div>
  );
}

function ProviderRow({ provider, row }) {
  const decisions = row?.decisions || {};
  return (
    <div className="grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(68px,0.7fr))] items-center gap-2 border-b border-border py-2.5 text-xs last:border-b-0">
      <div className="truncate font-semibold text-ink">{providerLabel(provider)}</div>
      <div className="font-mono text-slate-600">{number(decisions.decision_count)} decisions</div>
      <div className="font-mono text-slate-600">{number(decisions.trade_count)} trades</div>
      <div className="font-mono text-slate-600">{percent(decisions.citation_rate)} cited</div>
      <div className="font-mono text-[11px] text-slate-500">{percent(decisions.avg_confidence, 0)} confidence</div>
    </div>
  );
}

export default function AgentReadout({ report, loading }) {
  const totals = report?.decisions?.totals || {};
  const benchmark = report?.benchmark_comparison;
  const byBenchmark = benchmark?.by_benchmark || {};
  const byProvider = report?.by_provider || {};
  const holdCause = topHoldCause(totals.hold_cause_counts);
  const sample = report?.sample || {};

  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
            Agent readout
            <InfoTooltip label="What is this readout?">
              This is the public learning loop: portfolio results, decision behavior, evidence use, and benchmark-relative outcomes. It shows summarized rationales and telemetry, never hidden chain-of-thought.
            </InfoTooltip>
          </div>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink">What the agents are doing and what to improve</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
            Read the chart first, then use the tape and pipeline below it to connect a portfolio move to the agent&apos;s evidence, risk gate, and execution result.
          </p>
        </div>
        <span className="w-fit rounded-md bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800">
          {loading ? "Loading evaluation" : report?.mode === "decision_grade" ? "Decision grade" : "Monitoring only"}
        </span>
      </div>

      {report ? (
        <>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            <Metric label="Decisions" value={number(totals.decision_count)} detail={`${number(totals.trade_count)} trades · ${number(totals.hold_count)} holds`} />
            <Metric label="Evidence-backed trades" value={percent(totals.citation_rate)} detail={`${number(totals.citation_count)} citations`} tone={Number(totals.citation_rate) > 0 ? "text-emerald-700" : "text-amber-700"} />
            <Metric label="Most common hold" value={holdCause} detail="Why the gate said wait" />
            <Metric label="Avg confidence" value={percent(totals.avg_confidence, 0)} detail="Model-reported confidence" />
            <Metric label="Risk blocked" value={number(report.risk_blocked?.blocked_count)} detail="Rejected before execution" />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-md border border-border bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Benchmark lens</div>
                  <p className="mt-1 text-sm text-slate-600">Are the trades adding value beyond simply holding the market?</p>
                </div>
                <span className="font-mono text-[11px] text-slate-500">{number(sample.labeled_decision_count)} labeled / {number(sample.decision_count)} decisions</span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <BenchmarkCard ticker="SPY" row={byBenchmark.SPY} />
                <BenchmarkCard ticker="QQQ" row={byBenchmark.QQQ} />
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-500">
                These comparisons are based on evaluated trade windows. They are the honest benchmark signal while the longer portfolio history is still accumulating.
              </p>
            </div>

            <div className="rounded-md border border-border bg-slate-50 p-3">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Improvement queue</div>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                {report.conclusion?.message || "Keep collecting decisions before changing the strategy."}
              </p>
              <div className="mt-3 border-t border-border pt-3 text-xs leading-5 text-slate-500">
                The next useful experiment is to compare each personality&apos;s action mix, evidence quality, and benchmark-relative outcome in the Research tabs before tuning prompts or risk limits.
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-md border border-border px-3 py-2 overflow-x-auto">
            <div className="grid min-w-[650px] grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(68px,0.7fr))] gap-2 border-b border-border pb-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
              <span>Agent family</span><span>Decisions</span><span>Trades</span><span>Evidence</span><span>Confidence</span>
            </div>
            <div className="min-w-[650px]">
              {Object.entries(byProvider).map(([provider, row]) => <ProviderRow key={provider} provider={provider} row={row} />)}
            </div>
          </div>
        </>
      ) : (
        <div className="mt-4 rounded-md border border-border bg-slate-50 px-4 py-5 text-sm text-slate-500">
          Waiting for the live evaluation report. The decision tape below will still show new agent events as they arrive.
        </div>
      )}
    </section>
  );
}
