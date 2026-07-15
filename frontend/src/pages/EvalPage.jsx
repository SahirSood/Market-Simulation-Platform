import { useEffect, useState } from "react";
import { getEvaluationSummary, getReplayRun, getReplayRuns } from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function shortId(value) {
  if (!value) return "";
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function yesNo(value) {
  if (value === null || value === undefined) return "n/a";
  return value ? "yes" : "no";
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

function DecisionRow({ row }) {
  const riskClass =
    row.risk_approved === false
      ? "text-[#EF4444]"
      : row.risk_approved === true
        ? "text-[#22C55E]"
        : "text-[#64748B]";
  return (
    <div className="grid grid-cols-[72px_110px_1fr_96px_96px_96px_1.4fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div className="font-mono text-[#64748B]">#{row.event_index}</div>
      <div className="text-[#F1F5F9]">{row.bot_name}</div>
      <div>
        <div className="text-[#CBD5E1]">
          {row.action} {row.quantity || ""} {row.ticker || ""}
        </div>
        <div className="text-[#64748B] text-xs font-mono">
          {row.llm_provider}
        </div>
      </div>
      <div className={riskClass}>{yesNo(row.risk_approved)}</div>
      <div className="text-[#CBD5E1]">{row.fill_qty_total || 0}</div>
      <div className="text-[#CBD5E1]">{(row.evidence_ids || []).length}</div>
      <div>
        <div className="text-[#CBD5E1] truncate">{row.reasoning}</div>
        {row.risk_reason && (
          <div className="text-[#64748B] text-xs truncate">{row.risk_reason}</div>
        )}
      </div>
    </div>
  );
}

function RunDetail({ detail, loading, error }) {
  if (loading) {
    return <Skeleton className="h-[320px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-5 py-3 text-sm text-[#EF4444]">
        {error}
      </section>
    );
  }
  if (!detail) {
    return null;
  }

  const run = detail.run;
  const totals = detail.summary?.totals || {};

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-[#F1F5F9]">{run.name}</h2>
          <div className="mt-1 text-[#64748B] text-xs font-mono">
            {shortId(run.id)} | {run.status} | {run.decision_count} decisions
          </div>
        </div>
        <div className="text-right text-[#64748B] text-xs">
          {run.started_at ? new Date(run.started_at).toLocaleString() : ""}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-5 border-b border-border">
        <Metric label="Run Citation" value={pct(totals.citation_rate)} />
        <Metric label="Run Spec" value={pct(totals.speculative_trade_rate)} />
        <Metric label="Run Unsupported" value={pct(totals.unsupported_trade_rate)} />
        <Metric label="Run Fill" value={pct(totals.fill_rate)} />
      </div>

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-6 gap-3 py-2 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
            <div>Provider</div>
            <div>Decisions</div>
            <div>Trades</div>
            <div>Cited</div>
            <div>Spec</div>
            <div>Unsupported</div>
          </div>
          {(detail.provider_comparison || []).map((row) => (
            <ProviderRow key={row.group} row={row} />
          ))}
        </div>
      </div>

      <div className="px-5 py-4 overflow-x-auto">
        <div className="min-w-[980px]">
          <div className="grid grid-cols-[72px_110px_1fr_96px_96px_96px_1.4fr] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
            <div>Event</div>
            <div>Bot</div>
            <div>Order</div>
            <div>Risk</div>
            <div>Filled</div>
            <div>Cites</div>
            <div>Reason</div>
          </div>
          {(detail.decisions || []).length === 0 ? (
            <div className="py-5 text-sm text-[#64748B]">No replay decisions stored.</div>
          ) : (
            detail.decisions.map((row) => <DecisionRow key={row.id} row={row} />)
          )}
        </div>
      </div>
    </section>
  );
}

export default function EvalPage() {
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
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

  async function loadRunDetail(runId) {
    try {
      setSelectedRunId(runId);
      setDetailLoading(true);
      setDetailError(null);
      const detail = await getReplayRun(runId);
      setRunDetail(detail);
    } catch (err) {
      setRunDetail(null);
      setDetailError(err.message || "Failed to load replay run");
    } finally {
      setDetailLoading(false);
    }
  }

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
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => loadRunDetail(run.id)}
                    className={[
                      "w-full text-left py-4 grid grid-cols-1 md:grid-cols-4 gap-3 md:gap-4 text-sm transition-colors",
                      selectedRunId === run.id ? "bg-[#111827]" : "hover:bg-[#0F172A]",
                    ].join(" ")}
                  >
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
                  </button>
                ))
              )}
            </div>
          </section>

          <RunDetail
            detail={runDetail}
            loading={detailLoading}
            error={detailError}
          />
        </>
      )}
    </div>
  );
}
