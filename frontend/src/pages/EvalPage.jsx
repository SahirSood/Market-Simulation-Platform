import { useEffect, useState } from "react";
import { getEvaluationSummary, getReplayRuns } from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function Metric({ label, value, sub }) {
  return (
    <div className="bg-panel border border-border rounded-lg p-4 min-h-[104px]">
      <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">
        {label}
      </div>
      <div className="mt-3 text-[#F1F5F9] text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-[#64748B] text-xs">{sub}</div>}
    </div>
  );
}

function ProviderRow({ row }) {
  return (
    <div className="grid grid-cols-6 items-center gap-3 border-b border-border last:border-b-0 py-3 text-sm">
      <div className="font-mono text-[#F1F5F9] capitalize">{row.group}</div>
      <div className="text-[#CBD5E1]">{row.decision_count}</div>
      <div className="text-[#CBD5E1]">{row.trade_count}</div>
      <div className="text-[#22C55E]">{pct(row.citation_rate)}</div>
      <div className="text-[#F97316]">{pct(row.speculative_trade_rate)}</div>
      <div className="text-[#EF4444]">{pct(row.unsupported_trade_rate)}</div>
    </div>
  );
}

export default function EvalPage() {
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const [summaryData, runData] = await Promise.all([
          getEvaluationSummary(),
          getReplayRuns(),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setRuns(runData);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load evaluation data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const totals = summary?.totals;

  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-[#F1F5F9] font-semibold text-lg">Evaluation</h1>
        <p className="text-[#64748B] text-sm mt-1">
          Evidence citations, speculative trades, unsupported decisions, and replay run tracking.
        </p>
      </div>

      {error && (
        <div className="bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-5 py-3 text-sm text-[#EF4444]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[104px] rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Metric
              label="Citation Rate"
              value={pct(totals?.citation_rate)}
              sub={`${totals?.evidence_backed_trade_count || 0} evidence-backed trades`}
            />
            <Metric
              label="Speculative"
              value={pct(totals?.speculative_trade_rate)}
              sub={`${totals?.speculative_trade_count || 0} speculative trades`}
            />
            <Metric
              label="Unsupported"
              value={pct(totals?.unsupported_trade_rate)}
              sub={`${totals?.unsupported_trade_count || 0} trades without citations`}
            />
            <Metric
              label="Fill Rate"
              value={pct(totals?.fill_rate)}
              sub={`${totals?.trade_count || 0} total trade decisions`}
            />
          </div>

          <section className="bg-panel border border-border rounded-lg overflow-x-auto">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-[#F1F5F9]">Provider Comparison</h2>
            </div>
            <div className="px-5 min-w-[720px]">
              <div className="grid grid-cols-6 gap-3 py-3 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
                <div>Provider</div>
                <div>Decisions</div>
                <div>Trades</div>
                <div>Cited</div>
                <div>Spec</div>
                <div>Unsupported</div>
              </div>
              {(summary?.provider_comparison || []).map((row) => (
                <ProviderRow key={row.group} row={row} />
              ))}
            </div>
          </section>

          <section className="bg-panel border border-border rounded-lg">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-[#F1F5F9]">Replay Runs</h2>
            </div>
            <div className="px-5 divide-y divide-border">
              {runs.length === 0 ? (
                <div className="py-5 text-sm text-[#64748B]">No replay runs recorded yet.</div>
              ) : (
                runs.map((run) => (
                  <div key={run.id} className="py-4 grid grid-cols-1 md:grid-cols-4 gap-3 md:gap-4 text-sm">
                    <div>
                      <div className="text-[#F1F5F9]">{run.name}</div>
                      <div className="text-[#64748B] text-xs font-mono">{run.status}</div>
                    </div>
                    <div className="text-[#CBD5E1]">{run.decision_count} decisions</div>
                    <div className="text-[#64748B] font-mono text-xs truncate">
                      {run.input_fingerprint}
                    </div>
                    <div className="text-[#64748B] text-xs text-right">
                      {run.started_at ? new Date(run.started_at).toLocaleString() : ""}
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
