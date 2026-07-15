import { useEffect, useState } from "react";
import {
  getEvaluationSummary,
  getEvidenceChunks,
  getReplayRun,
  getReplayRunComparison,
  getReplayRuns,
} from "../api/endpoints";
import EvidenceDrawer from "../components/evaluation/EvidenceDrawer";
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

function money(value) {
  if (value === null || value === undefined) return "n/a";
  return `$${Math.round(value).toLocaleString()}`;
}

function signedMoney(value) {
  if (value === null || value === undefined) return "n/a";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${money(value)}`;
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

function ComparisonRunRow({ row }) {
  const metrics = row.metrics || {};
  return (
    <div className="grid grid-cols-[1.4fr_90px_90px_90px_90px_100px_118px_118px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div>
        <div className="text-[#F1F5F9] truncate">{row.run?.name}</div>
        <div className="text-[#64748B] text-xs font-mono truncate">
          {shortId(row.run?.id)} | {row.run?.status}
        </div>
      </div>
      <div className="text-[#CBD5E1]">{metrics.decision_count || 0}</div>
      <div className="text-[#CBD5E1]">{metrics.trade_count || 0}</div>
      <div className="text-[#22C55E]">{pct(metrics.citation_rate)}</div>
      <div className="text-[#EF4444]">{pct(metrics.risk_rejection_rate)}</div>
      <div className="text-[#CBD5E1]">{metrics.filled_quantity || 0}</div>
      <div className="font-mono text-[#CBD5E1]">{money(metrics.final_portfolio_value)}</div>
      <div
        className={[
          "font-mono",
          (metrics.portfolio_value_change || 0) >= 0 ? "text-[#22C55E]" : "text-[#EF4444]",
        ].join(" ")}
      >
        {signedMoney(metrics.portfolio_value_change)}
      </div>
    </div>
  );
}

function ComparisonProviderRow({ row }) {
  return (
    <div className="grid grid-cols-[1.2fr_110px_90px_90px_90px_90px_110px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div>
        <div className="text-[#F1F5F9] capitalize">{row.provider}</div>
        <div className="text-[#64748B] text-xs truncate">{row.run_name}</div>
      </div>
      <div className="text-[#CBD5E1]">{row.decision_count}</div>
      <div className="text-[#CBD5E1]">{row.trade_count}</div>
      <div className="text-[#22C55E]">{pct(row.citation_rate)}</div>
      <div className="text-[#F97316]">{pct(row.speculative_trade_rate)}</div>
      <div className="text-[#EF4444]">{pct(row.unsupported_trade_rate)}</div>
      <div className="text-[#EF4444]">{pct(row.risk_rejection_rate)}</div>
    </div>
  );
}

function ReplayComparison({ comparison, loading, error }) {
  if (loading) {
    return <Skeleton className="h-[360px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-5 py-3 text-sm text-[#EF4444]">
        {error}
      </section>
    );
  }
  if (!comparison) {
    return null;
  }

  const runCount = comparison.run_count || 0;

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-[#F1F5F9]">Replay Comparison</h2>
          <div className="mt-1 text-[#64748B] text-xs font-mono">
            {runCount} runs | {comparison.input_fingerprint}
          </div>
        </div>
      </div>

      {runCount < 2 && (
        <div className="mx-5 mt-5 rounded-lg border border-[#F97316]/30 bg-[#431407] px-4 py-3 text-sm text-[#FDBA74]">
          Only one run exists for this input fingerprint. Add another replay with the same events to compare models.
        </div>
      )}

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[980px]">
          <div className="grid grid-cols-[1.4fr_90px_90px_90px_90px_100px_118px_118px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
            <div>Run</div>
            <div>Decisions</div>
            <div>Trades</div>
            <div>Cited</div>
            <div>Risk Rej</div>
            <div>Filled</div>
            <div>Final Value</div>
            <div>Change</div>
          </div>
          {(comparison.runs || []).map((row) => (
            <ComparisonRunRow key={row.run?.id} row={row} />
          ))}
        </div>
      </div>

      <div className="px-5 py-4 overflow-x-auto">
        <div className="min-w-[860px]">
          <div className="grid grid-cols-[1.2fr_110px_90px_90px_90px_90px_110px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
            <div>Provider</div>
            <div>Decisions</div>
            <div>Trades</div>
            <div>Cited</div>
            <div>Spec</div>
            <div>Unsupported</div>
            <div>Risk Rej</div>
          </div>
          {(comparison.by_provider || []).length === 0 ? (
            <div className="py-5 text-sm text-[#64748B]">No provider comparison rows available.</div>
          ) : (
            comparison.by_provider.map((row) => (
              <ComparisonProviderRow
                key={`${row.run_id}-${row.provider}`}
                row={row}
              />
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function EvidenceButton({ ids, onOpen }) {
  const count = ids?.length || 0;
  if (count === 0) {
    return <span className="text-[#64748B]">0</span>;
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(ids)}
      className="text-claude hover:text-[#93C5FD]"
    >
      {count}
    </button>
  );
}

function DecisionRow({ row, onOpenEvidence }) {
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
      <div>
        <EvidenceButton ids={row.evidence_ids} onOpen={onOpenEvidence} />
      </div>
      <div>
        <div className="text-[#CBD5E1] truncate">{row.reasoning}</div>
        {row.risk_reason && (
          <div className="text-[#64748B] text-xs truncate">{row.risk_reason}</div>
        )}
      </div>
    </div>
  );
}

function RunDetail({ detail, loading, error, onOpenEvidence }) {
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
            detail.decisions.map((row) => (
              <DecisionRow
                key={row.id}
                row={row}
                onOpenEvidence={onOpenEvidence}
              />
            ))
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
  const [comparison, setComparison] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [evidence, setEvidence] = useState({
    open: false,
    loading: false,
    error: null,
    data: null,
  });

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
      setComparisonLoading(true);
      setDetailError(null);
      setComparisonError(null);
      const [detail, comparisonData] = await Promise.all([
        getReplayRun(runId),
        getReplayRunComparison({ runId }),
      ]);
      setRunDetail(detail);
      setComparison(comparisonData);
    } catch (err) {
      setRunDetail(null);
      setComparison(null);
      setDetailError(err.message || "Failed to load replay run");
      setComparisonError(err.message || "Failed to load replay comparison");
    } finally {
      setDetailLoading(false);
      setComparisonLoading(false);
    }
  }

  async function openEvidence(ids) {
    setEvidence({ open: true, loading: true, error: null, data: null });
    const data = await getEvidenceChunks(ids);
    if (!data) {
      setEvidence({
        open: true,
        loading: false,
        error: "Failed to load evidence chunks",
        data: null,
      });
      return;
    }
    setEvidence({ open: true, loading: false, error: null, data });
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

          <ReplayComparison
            comparison={comparison}
            loading={comparisonLoading}
            error={comparisonError}
          />

          <RunDetail
            detail={runDetail}
            loading={detailLoading}
            error={detailError}
            onOpenEvidence={openEvidence}
          />
        </>
      )}

      <EvidenceDrawer
        open={evidence.open}
        loading={evidence.loading}
        error={evidence.error}
        data={evidence.data}
        onClose={() => setEvidence({ open: false, loading: false, error: null, data: null })}
      />
    </div>
  );
}
