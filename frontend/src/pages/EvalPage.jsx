import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getEvaluationSummary,
  getEvidenceChunks,
  getRiskRejections,
  getReplayRun,
  getReplayRunComparison,
  getReplayRuns,
} from "../api/endpoints";
import EvidenceDrawer from "../components/evaluation/EvidenceDrawer";
import InfoTooltip from "../components/ui/InfoTooltip";
import Skeleton from "../components/ui/Skeleton";
import { downloadCsv, downloadJson, flattenForCsv } from "../lib/exportUtils";

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
      <div className="text-slate-500 text-xs font-mono uppercase tracking-widest">
        {label}
      </div>
      <div className="mt-3 text-ink text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-slate-500 text-xs">{sub}</div>}
    </div>
  );
}

function ExportButton({ children, onClick, disabled = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "px-3 py-2 rounded-md border border-border text-xs font-mono transition-colors",
        disabled
          ? "text-slate-400 cursor-not-allowed"
          : "text-slate-700 hover:bg-slate-100",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function ChartPanel({ title, children }) {
  return (
    <section className="bg-panel border border-border rounded-lg p-5 min-h-[320px]">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <div className="mt-4 h-[250px]">{children}</div>
    </section>
  );
}

function EvidenceUsageChart({ totals }) {
  const counts = totals?.status_counts || {};
  const rows = [
    { status: "cited", count: (counts.evidence_backed || 0) + (counts.speculative_evidence_backed || 0) },
    { status: "spec", count: counts.speculative || 0 },
    { status: "unsupported", count: counts.unsupported || 0 },
    { status: "hold", count: counts.hold || 0 },
  ];
  return (
    <ChartPanel title="Evidence Usage">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis dataKey="status" stroke="#94A3B8" tickLine={false} />
          <YAxis stroke="#94A3B8" allowDecimals={false} tickLine={false} />
          <Tooltip cursor={{ fill: "#F8FAFC" }} contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }} />
          <Bar dataKey="count" fill="#2563EB" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartPanel>
  );
}

function ReplayComparisonChart({ comparison }) {
  const rows = (comparison?.runs || []).map((row) => ({
    run: row.run?.name || shortId(row.run?.id),
    cited: Math.round((row.metrics?.citation_rate || 0) * 100),
    risk: Math.round((row.metrics?.risk_rejection_rate || 0) * 100),
    fill: Math.round((row.metrics?.fill_rate || 0) * 100),
  }));
  if (rows.length === 0) return null;
  return (
    <ChartPanel title="Replay Rates">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis dataKey="run" stroke="#94A3B8" tickLine={false} tick={{ fontSize: 11 }} />
          <YAxis stroke="#94A3B8" tickLine={false} tickFormatter={(value) => `${value}%`} />
          <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }} />
          <Bar dataKey="cited" fill="#16A34A" radius={[4, 4, 0, 0]} />
          <Bar dataKey="risk" fill="#DC2626" radius={[4, 4, 0, 0]} />
          <Bar dataKey="fill" fill="#2563EB" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartPanel>
  );
}

function replayComparisonRunRows(comparison) {
  return (comparison?.runs || []).map((row) =>
    flattenForCsv({
      run_id: row.run?.id,
      run_name: row.run?.name,
      run_status: row.run?.status,
      input_fingerprint: row.run?.input_fingerprint,
      metrics: row.metrics || {},
    }),
  );
}

function replayComparisonProviderRows(comparison) {
  return (comparison?.by_provider || []).map((row) => flattenForCsv(row));
}

function runDecisionRows(detail) {
  return (detail?.decisions || []).map((row) => flattenForCsv(row));
}

function riskRejectionRows(data) {
  return (data?.decisions || []).map((row) => flattenForCsv(row));
}

function ProviderRow({ row }) {
  return (
    <div className="grid grid-cols-6 items-center gap-3 border-b border-border last:border-b-0 py-3 text-sm">
      <div className="font-mono text-ink capitalize">{row.group}</div>
      <div className="text-slate-700">{row.decision_count}</div>
      <div className="text-slate-700">{row.trade_count}</div>
      <div className="text-emerald-600">{pct(row.citation_rate)}</div>
      <div className="text-orange-600">{pct(row.speculative_trade_rate)}</div>
      <div className="text-rose-600">{pct(row.unsupported_trade_rate)}</div>
    </div>
  );
}

function ComparisonRunRow({ row }) {
  const metrics = row.metrics || {};
  return (
    <div className="grid grid-cols-[1.4fr_90px_90px_90px_90px_100px_118px_118px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div>
        <div className="text-ink truncate">{row.run?.name}</div>
        <div className="text-slate-500 text-xs font-mono truncate">
          {shortId(row.run?.id)} | {row.run?.status}
        </div>
      </div>
      <div className="text-slate-700">{metrics.decision_count || 0}</div>
      <div className="text-slate-700">{metrics.trade_count || 0}</div>
      <div className="text-emerald-600">{pct(metrics.citation_rate)}</div>
      <div className="text-rose-600">{pct(metrics.risk_rejection_rate)}</div>
      <div className="text-slate-700">{metrics.filled_quantity || 0}</div>
      <div className="font-mono text-slate-700">{money(metrics.final_portfolio_value)}</div>
      <div
        className={[
          "font-mono",
          (metrics.portfolio_value_change || 0) >= 0 ? "text-emerald-600" : "text-rose-600",
        ].join(" ")}
      >
        {signedMoney(metrics.portfolio_value_change)}
      </div>
    </div>
  );
}

function configSummary(run) {
  const config = run?.config || {};
  const modelConfig = config.model_config || {};
  const bots = modelConfig.bots || [];
  const providers = [...new Set(bots.map((bot) => bot.provider).filter(Boolean))];
  const models = [...new Set(bots.map((bot) => bot.model).filter(Boolean))];
  const promptHashes = [...new Set(bots.map((bot) => bot.prompt_hash).filter(Boolean))];
  return {
    providers: providers.join(", ") || (config.providers || []).join(", ") || "n/a",
    models: models.join(", ") || "n/a",
    prompt: promptHashes.length === 1 ? shortId(promptHashes[0]) : `${promptHashes.length} hashes`,
    tools: bots.some((bot) => bot.tool_mode_enabled) ? "on" : "off",
  };
}

function ReplayConfigDiff({ comparison }) {
  const rows = (comparison?.runs || []).map((row) => ({
    run: row.run,
    summary: configSummary(row.run),
  }));
  if (rows.length === 0) return null;
  return (
    <div className="px-5 py-4 border-b border-border overflow-x-auto">
      <div className="min-w-[820px]">
        <div className="grid grid-cols-[1.3fr_1fr_1.4fr_120px_90px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
          <div>Run</div>
          <div>Providers</div>
          <div>Models</div>
          <div>Prompt</div>
          <div>Tools</div>
        </div>
        {rows.map(({ run, summary }) => (
          <div key={run?.id} className="grid grid-cols-[1.3fr_1fr_1.4fr_120px_90px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
            <div className="text-ink truncate">{run?.name}</div>
            <div className="text-slate-700 truncate">{summary.providers}</div>
            <div className="text-slate-700 font-mono truncate">{summary.models}</div>
            <div className="text-slate-500 font-mono">{summary.prompt}</div>
            <div className={summary.tools === "on" ? "text-emerald-600" : "text-slate-500"}>{summary.tools}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ComparisonProviderRow({ row }) {
  return (
    <div className="grid grid-cols-[1.2fr_110px_90px_90px_90px_90px_110px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div>
        <div className="text-ink capitalize">{row.provider}</div>
        <div className="text-slate-500 text-xs truncate">{row.run_name}</div>
      </div>
      <div className="text-slate-700">{row.decision_count}</div>
      <div className="text-slate-700">{row.trade_count}</div>
      <div className="text-emerald-600">{pct(row.citation_rate)}</div>
      <div className="text-orange-600">{pct(row.speculative_trade_rate)}</div>
      <div className="text-rose-600">{pct(row.unsupported_trade_rate)}</div>
      <div className="text-rose-600">{pct(row.risk_rejection_rate)}</div>
    </div>
  );
}

function ReplayComparison({ comparison, loading, error }) {
  if (loading) {
    return <Skeleton className="h-[360px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
        {error}
      </section>
    );
  }
  if (!comparison) {
    return null;
  }

  const runCount = comparison.run_count || 0;
  const runRows = replayComparisonRunRows(comparison);
  const providerRows = replayComparisonProviderRows(comparison);

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Replay Comparison</h2>
          <div className="mt-1 text-slate-500 text-xs font-mono">
            {runCount} runs | {comparison.input_fingerprint}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <ExportButton onClick={() => downloadJson("replay-comparison", comparison)}>
            JSON
          </ExportButton>
          <ExportButton onClick={() => downloadCsv("replay-comparison-runs", runRows)}>
            Runs CSV
          </ExportButton>
          <ExportButton onClick={() => downloadCsv("replay-comparison-providers", providerRows)}>
            Providers CSV
          </ExportButton>
        </div>
      </div>

      {runCount < 2 && (
        <div className="mx-5 mt-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          Only one run exists for this input fingerprint. Add another replay with the same events to compare models.
        </div>
      )}

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[980px]">
          <div className="grid grid-cols-[1.4fr_90px_90px_90px_90px_100px_118px_118px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
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

      <ReplayConfigDiff comparison={comparison} />

      <div className="px-5 py-4 overflow-x-auto">
        <div className="min-w-[860px]">
          <div className="grid grid-cols-[1.2fr_110px_90px_90px_90px_90px_110px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Provider</div>
            <div>Decisions</div>
            <div>Trades</div>
            <div>Cited</div>
            <div>Spec</div>
            <div>Unsupported</div>
            <div>Risk Rej</div>
          </div>
          {(comparison.by_provider || []).length === 0 ? (
            <div className="py-5 text-sm text-slate-500">No provider comparison rows available.</div>
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

function RiskRejectionPanel({ data }) {
  const rows = Object.values(
    (data?.decisions || []).reduce((acc, row) => {
      const key = row.bot_id || "unknown";
      acc[key] ||= {
        bot_id: key,
        bot_name: row.bot_name || key,
        count: 0,
      };
      acc[key].count += 1;
      return acc;
    }, {})
  ).sort((a, b) => b.count - a.count);
  const maxCount = Math.max(1, ...rows.map((row) => row.count));
  const exportRows = riskRejectionRows(data);

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <h2 className="text-sm font-semibold text-ink">Risk Rejections</h2>
        <div className="flex flex-wrap gap-2 justify-end">
          <ExportButton
            disabled={exportRows.length === 0}
            onClick={() => downloadCsv("risk-rejections", exportRows)}
          >
            CSV
          </ExportButton>
        </div>
      </div>
      <div className="p-5 space-y-3">
        {rows.length === 0 ? (
          <div className="text-sm text-slate-500">No recent risk rejections.</div>
        ) : (
          rows.map((row) => (
            <div key={row.bot_id} className="grid grid-cols-[180px_1fr_44px] gap-3 items-center text-sm">
              <div className="text-slate-700 truncate">{row.bot_name}</div>
              <div className="h-2 bg-slate-100 rounded">
                <div
                  className="h-2 bg-rose-600 rounded"
                  style={{ width: `${Math.max(8, (row.count / maxCount) * 100)}%` }}
                />
              </div>
              <div className="text-rose-600 text-right font-mono">{row.count}</div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function EvidenceButton({ ids, onOpen }) {
  const count = ids?.length || 0;
  if (count === 0) {
    return <span className="text-slate-500">0</span>;
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(ids)}
      className="text-claude hover:text-blue-500"
    >
      {count}
    </button>
  );
}

function DecisionRow({ row, onOpenEvidence }) {
  const riskClass =
    row.risk_approved === false
      ? "text-rose-600"
      : row.risk_approved === true
        ? "text-emerald-600"
        : "text-slate-500";
  return (
    <div className="grid grid-cols-[72px_110px_1fr_96px_96px_96px_1.4fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div className="font-mono text-slate-500">#{row.event_index}</div>
      <div className="text-ink">{row.bot_name}</div>
      <div>
        <div className="text-slate-700">
          {row.action} {row.quantity || ""} {row.ticker || ""}
        </div>
        <div className="text-slate-500 text-xs font-mono">
          {row.llm_provider}
        </div>
      </div>
      <div className={riskClass}>{yesNo(row.risk_approved)}</div>
      <div className="text-slate-700">{row.fill_qty_total || 0}</div>
      <div>
        <EvidenceButton ids={row.evidence_ids} onOpen={onOpenEvidence} />
      </div>
      <div>
        <div className="text-slate-700 truncate">{row.reasoning}</div>
        {row.risk_reason && (
          <div className="text-slate-500 text-xs truncate">{row.risk_reason}</div>
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
      <section className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
        {error}
      </section>
    );
  }
  if (!detail) {
    return null;
  }

  const run = detail.run;
  const totals = detail.summary?.totals || {};
  const decisionRows = runDecisionRows(detail);

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">{run.name}</h2>
          <div className="mt-1 text-slate-500 text-xs font-mono">
            {shortId(run.id)} | {run.status} | {run.decision_count} decisions
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="text-right text-slate-500 text-xs">
            {run.started_at ? new Date(run.started_at).toLocaleString() : ""}
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <ExportButton onClick={() => downloadJson("replay-run-detail", detail)}>
              JSON
            </ExportButton>
            <ExportButton
              disabled={decisionRows.length === 0}
              onClick={() => downloadCsv("replay-run-decisions", decisionRows)}
            >
              Decisions CSV
            </ExportButton>
          </div>
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
          <div className="grid grid-cols-6 gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
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
          <div className="grid grid-cols-[72px_110px_1fr_96px_96px_96px_1.4fr] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Event</div>
            <div>Bot</div>
            <div>Order</div>
            <div>Risk</div>
            <div>Filled</div>
            <div>Cites</div>
            <div>Reason</div>
          </div>
          {(detail.decisions || []).length === 0 ? (
            <div className="py-5 text-sm text-slate-500">No replay decisions stored.</div>
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
  const [riskRejections, setRiskRejections] = useState(null);
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
        const [summaryData, runData, riskData] = await Promise.all([
          getEvaluationSummary(),
          getReplayRuns(),
          getRiskRejections(100),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setRuns(runData);
          setRiskRejections(riskData);
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
  const providerRows = summary?.provider_comparison || [];

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
    <div className="mx-auto max-w-[1280px] space-y-5 px-4 py-6 md:space-y-6 md:px-8 md:py-8">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Evaluation</h1>
            <InfoTooltip label="What is evaluation for?">
              Evaluation checks whether trades cite evidence, whether speculative behavior is labeled, how often risk
              rejects orders, and whether replay runs reproduce expected behavior.
            </InfoTooltip>
          </div>
          <p className="text-slate-500 text-sm mt-1">
            Evidence citations, speculative trades, unsupported decisions, and replay run tracking.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ExportButton
            disabled={loading || !summary}
            onClick={() => downloadJson("evaluation-summary", summary)}
          >
            JSON
          </ExportButton>
          <ExportButton
            disabled={loading || providerRows.length === 0}
            onClick={() => downloadCsv("evaluation-providers", providerRows)}
          >
            Providers CSV
          </ExportButton>
        </div>
      </div>

      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <EvidenceUsageChart totals={totals} />
            <RiskRejectionPanel data={riskRejections} />
          </div>

          <section className="bg-panel border border-border rounded-lg overflow-x-auto">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-ink">Provider Comparison</h2>
            </div>
            <div className="px-5 min-w-[720px]">
              <div className="grid grid-cols-6 gap-3 py-3 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
                <div>Provider</div>
                <div>Decisions</div>
                <div>Trades</div>
                <div>Cited</div>
                <div>Spec</div>
                <div>Unsupported</div>
              </div>
              {providerRows.length === 0 ? (
                <div className="py-5 text-sm text-slate-500">No provider comparison rows available.</div>
              ) : (
                providerRows.map((row) => (
                  <ProviderRow key={row.group} row={row} />
                ))
              )}
            </div>
          </section>

          <section className="bg-panel border border-border rounded-lg">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-ink">Replay Runs</h2>
            </div>
            <div className="px-5 divide-y divide-border">
              {runs.length === 0 ? (
                <div className="py-5 text-sm text-slate-500">No replay runs recorded yet.</div>
              ) : (
                runs.map((run) => (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => loadRunDetail(run.id)}
                    className={[
                      "w-full text-left py-4 grid grid-cols-1 md:grid-cols-4 gap-3 md:gap-4 text-sm transition-colors",
                      selectedRunId === run.id ? "bg-slate-100" : "hover:bg-slate-50",
                    ].join(" ")}
                  >
                    <div>
                      <div className="text-ink">{run.name}</div>
                      <div className="text-slate-500 text-xs font-mono">{run.status}</div>
                    </div>
                    <div className="text-slate-700">{run.decision_count} decisions</div>
                    <div className="text-slate-500 font-mono text-xs truncate">
                      {run.input_fingerprint}
                    </div>
                    <div className="text-slate-500 text-xs text-right">
                      {run.started_at ? new Date(run.started_at).toLocaleString() : ""}
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {!comparisonLoading && !comparisonError && (
            <ReplayComparisonChart comparison={comparison} />
          )}

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
