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
  getLiveEvaluationReport,
  getEvaluationSchedulerStatus,
  getEvidenceChunks,
  getOutcomeSummary,
  getRiskRejections,
  getRecentOutcomes,
  getReplayFixtures,
  getReplayResearch,
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

function money(value, digits = 0) {
  if (value === null || value === undefined) return "n/a";
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return "n/a";
  return numberValue.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function number(value, digits = 0) {
  if (value === null || value === undefined || value === "") return "n/a";
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return "n/a";
  return numberValue.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function rate(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "n/a";
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return "n/a";
  return `${(numberValue * 100).toFixed(digits)}%`;
}

function signedMoney(value, digits = 0) {
  if (value === null || value === undefined) return "n/a";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${money(value, digits)}`;
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

function formatDateTime(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "n/a";
  return date.toLocaleString();
}

function formatInterval(seconds) {
  const value = Number(seconds || 0);
  if (!Number.isFinite(value) || value <= 0) return "n/a";
  if (value >= 86400) return `${Math.round(value / 86400)}d`;
  if (value >= 3600) return `${Math.round(value / 3600)}h`;
  if (value >= 60) return `${Math.round(value / 60)}m`;
  return `${Math.round(value)}s`;
}

function statusClass(enabled, running) {
  if (enabled && running) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (enabled) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-slate-200 bg-slate-100 text-slate-600";
}

function SchedulerJobCard({ title, job, running }) {
  const enabled = Boolean(job?.enabled);
  const lastRun = job?.last_run || {};
  const count =
    title === "Outcome Labels"
      ? `${lastRun.created_count || 0} labels`
      : title === "Live Report"
        ? `${lastRun.labeled_decision_count || 0} labeled`
      : `${lastRun.run_count || 0} runs`;
  return (
    <div className="border border-border rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <div className="mt-1 text-xs text-slate-500 font-mono">
            every {formatInterval(job?.interval_seconds)}
          </div>
        </div>
        <span className={`rounded-md border px-2 py-1 text-xs font-mono ${statusClass(enabled, running)}`}>
          {enabled ? (running ? "on" : "queued") : "off"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 text-xs md:grid-cols-2">
        <div>
          <div className="font-mono uppercase tracking-widest text-slate-500">Next</div>
          <div className="mt-1 text-slate-700">{formatDateTime(job?.next_run_at)}</div>
        </div>
        <div>
          <div className="font-mono uppercase tracking-widest text-slate-500">Last</div>
          <div className="mt-1 text-slate-700">
            {lastRun.status ? `${lastRun.status} | ${count}` : "n/a"}
          </div>
        </div>
      </div>
    </div>
  );
}

function EvaluationAutomationPanel({ status }) {
  if (!status) return null;
  const configured = status.configured !== false;
  if (!configured) {
    return (
      <section className="bg-panel border border-border rounded-lg p-5">
        <h2 className="text-sm font-semibold text-ink">Evaluation Automation</h2>
        <div className="mt-2 text-sm text-slate-500">Scheduler is not configured.</div>
      </section>
    );
  }

  return (
    <section className="bg-panel border border-border rounded-lg p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink">Evaluation Automation</h2>
          <div className="mt-1 text-xs text-slate-500 font-mono">
            scheduler {status.running ? "running" : "stopped"}
          </div>
        </div>
        <span className={`w-fit rounded-md border px-2 py-1 text-xs font-mono ${statusClass(status.enabled, status.running)}`}>
          {status.enabled ? (status.running ? "active" : "enabled") : "disabled"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SchedulerJobCard
          title="Outcome Labels"
          job={status.outcome_labeling}
          running={status.running}
        />
        <SchedulerJobCard
          title="Live Report"
          job={status.live_report}
          running={status.running}
        />
        <SchedulerJobCard
          title="Replay Matrix"
          job={status.replay_matrix}
          running={status.running}
        />
      </div>
    </section>
  );
}

function LiveEvaluationPanel({ data, loading, error }) {
  if (loading) {
    return <Skeleton className="h-[250px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-panel border border-rose-200 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-ink">Live Evaluation Report</h2>
        <div className="mt-2 text-sm text-rose-600">{error}</div>
      </section>
    );
  }
  if (!data) return null;

  const sample = data.sample || {};
  const selected = data.outcomes?.selected?.totals || {};
  const decisionTotals = data.decisions?.totals || {};
  const costs = data.costs || {};
  const riskBlocked = data.risk_blocked || {};
  const benchmark = data.benchmark_comparison || {};
  const groups = Object.entries(data.by_bot || {});
  const status = data.mode === "decision_grade" ? "decision grade" : "monitoring only";
  const hasEvaluatedOutcomes = Number(selected.evaluated_trade_count || 0) > 0;
  const hasOutcomeLabels = Number(selected.outcome_count || 0) > 0;

  return (
    <section className="bg-panel border border-border rounded-lg p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink">Live Evaluation Report</h2>
          <div className="mt-1 text-xs text-slate-500 font-mono">
            {data.outcomes?.selected_horizon || "1d"} horizon | {data.window?.since ? formatDateTime(data.window.since) : "n/a"} to {data.window?.until ? formatDateTime(data.window.until) : "n/a"}
          </div>
        </div>
        <span className={`w-fit rounded-md border px-2 py-1 text-xs font-mono ${data.mode === "decision_grade" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
          {status}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Labeled" value={number(sample.labeled_decision_count)} sub={`of ${number(sample.decision_count)} decisions`} />
        <Metric label="Win Rate" value={hasEvaluatedOutcomes ? rate(selected.win_rate) : "n/a"} sub={`${number(selected.evaluated_trade_count)} evaluated`} />
        <Metric label="Net After Cost" value={hasOutcomeLabels ? signedMoney(selected.total_net_after_llm_cost) : "n/a"} sub={`${number(selected.outcome_count)} labels`} />
        <Metric label="LLM Cost" value={money(costs.total_estimated_cost_usd, 2)} sub={`${number(costs.llm_call_count)} calls`} />
        <Metric label="Risk Blocked" value={number(riskBlocked.blocked_count)} sub={riskBlocked.available ? "counterfactual marked" : "counterfactual pending"} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(240px,0.6fr)]">
        <div className="overflow-x-auto border border-border rounded-lg">
          <div className="px-4 py-3 border-b border-border text-xs font-mono uppercase tracking-widest text-slate-500">
            Bot readout
          </div>
          <div className="min-w-[560px]">
            <div className="grid grid-cols-5 gap-3 px-4 py-2 text-[11px] font-mono uppercase tracking-widest text-slate-500 border-b border-border">
              <div>Bot</div>
              <div>Decisions</div>
              <div>Trades</div>
              <div>Labels</div>
              <div>Net</div>
            </div>
            {groups.length === 0 ? (
              <div className="px-4 py-4 text-sm text-slate-500">No live rows in this window.</div>
            ) : (
              groups.map(([key, row]) => {
                const decisionsRow = row.decisions || {};
                const outcomesRow = row.outcomes || {};
                return (
                  <div key={key} className="grid grid-cols-5 gap-3 px-4 py-3 text-sm border-b border-border last:border-b-0">
                    <div className="truncate text-ink" title={decisionsRow.bot_name || key}>{decisionsRow.bot_name || key}</div>
                    <div className="text-slate-700">{number(decisionsRow.decision_count)}</div>
                    <div className="text-slate-700">{number(decisionsRow.trade_count)}</div>
                    <div className="text-slate-700">{number(outcomesRow.outcome_count)}</div>
                    <div className="text-slate-700">{signedMoney(outcomesRow.total_net_after_llm_cost)}</div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div className="border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Scope check</div>
            <div className="mt-2 text-slate-700">{(data.scope?.tradable_tickers || []).join(", ")}</div>
            <div className="mt-1 text-xs text-slate-500">Benchmarks: {(data.scope?.benchmark_tickers || []).join(", ")}</div>
          </div>
          <div className="border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Benchmark comparison</div>
            <div className="mt-2 text-slate-700">{benchmark.available ? "available" : "data-limited"}</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">{benchmark.reason}</div>
          </div>
          <div className="border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Readout</div>
            <div className="mt-2 text-xs leading-5 text-slate-600">{data.conclusion?.message}</div>
          </div>
        </div>
      </div>
    </section>
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
    <div className="grid grid-cols-[1.4fr_82px_78px_74px_76px_76px_104px_76px_112px_112px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
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
      <div className="text-slate-700">{pct(metrics.directional_accuracy)}</div>
      <div className={(metrics.intent_mark_pnl || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}>
        {signedMoney(metrics.intent_mark_pnl, 2)}
      </div>
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
        <div className="min-w-[1120px]">
          <div className="grid grid-cols-[1.4fr_82px_78px_74px_76px_76px_104px_76px_112px_112px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Run</div>
            <div>Decisions</div>
            <div>Trades</div>
            <div>Cited</div>
            <div>Risk Rej</div>
            <div>Dir Acc</div>
            <div>Intent PnL</div>
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

const OUTCOME_HORIZONS = ["immediate", "1h", "6h", "1d", "7d", "all"];

function outcomeStatusClass(status) {
  const key = String(status || "").toLowerCase();
  if (key === "profitable" || key === "filled") return "text-emerald-600";
  if (key === "unprofitable" || key === "risk_rejected" || key === "execution_error") return "text-rose-600";
  if (key === "not_filled" || key === "pending") return "text-amber-600";
  return "text-slate-600";
}

function outcomeBotRows(summary) {
  return Object.entries(summary?.by_bot || {})
    .map(([botId, row]) => ({ bot_id: botId, ...row }))
    .sort((a, b) => {
      const netA = Number(a.total_net_after_llm_cost || 0);
      const netB = Number(b.total_net_after_llm_cost || 0);
      if (netA !== netB) return netB - netA;
      return Number(b.win_rate || 0) - Number(a.win_rate || 0);
    });
}

function outcomeRecentRows(data) {
  return (data?.outcomes || []).map((row) => flattenForCsv(row));
}

function OutcomePanel({
  summary,
  recent,
  horizon,
  loading,
  error,
  onHorizonChange,
}) {
  if (loading) {
    return <Skeleton className="h-[420px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
        {error}
      </section>
    );
  }

  const totals = summary?.totals || {};
  const botRows = outcomeBotRows(summary);
  const recentRows = recent?.outcomes || [];
  const exportRows = outcomeRecentRows(recent);

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-1">
            <h2 className="text-sm font-semibold text-ink">Outcome Lab</h2>
            <InfoTooltip label="What is an outcome?">
              Outcome labels compare a logged decision with later market prices at fixed horizons, including PnL after
              estimated model cost.
            </InfoTooltip>
          </div>
          <div className="mt-1 text-slate-500 text-xs font-mono">
            {summary?.outcome_window?.returned || 0} rows | horizon {horizon}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end">
          {OUTCOME_HORIZONS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onHorizonChange(item)}
              className={[
                "rounded-md border px-3 py-2 text-xs font-mono transition-colors",
                horizon === item
                  ? "border-ink bg-ink text-white"
                  : "border-border text-slate-700 hover:bg-slate-100",
              ].join(" ")}
            >
              {item}
            </button>
          ))}
          <ExportButton onClick={() => downloadJson("outcome-summary", summary)}>
            JSON
          </ExportButton>
          <ExportButton
            disabled={exportRows.length === 0}
            onClick={() => downloadCsv("recent-outcomes", exportRows)}
          >
            CSV
          </ExportButton>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 p-5 border-b border-border md:grid-cols-5">
        <Metric label="Evaluated" value={totals.evaluated_trade_count || 0} sub={`${totals.outcome_count || 0} labels`} />
        <Metric label="Win Rate" value={pct(totals.win_rate)} sub={`${totals.profitable_count || 0} profitable`} />
        <Metric label="Net After Cost" value={signedMoney(totals.total_net_after_llm_cost, 2)} sub="PnL minus model spend" />
        <Metric label="Position PnL" value={signedMoney(totals.total_position_pnl, 2)} sub="Observed trade PnL" />
        <Metric label="LLM Cost" value={money(totals.total_llm_estimated_cost_usd, 4)} sub="Estimated spend" />
      </div>

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[860px]">
          <div className="grid grid-cols-[1.4fr_86px_86px_104px_104px_96px_104px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Bot</div>
            <div>Labels</div>
            <div>Wins</div>
            <div>Win Rate</div>
            <div>Net</div>
            <div>Risk Rej</div>
            <div>Cost</div>
          </div>
          {botRows.length === 0 ? (
            <div className="py-5 text-sm text-slate-500">No outcome labels recorded yet.</div>
          ) : (
            botRows.map((row) => (
              <div key={row.bot_id} className="grid grid-cols-[1.4fr_86px_86px_104px_104px_96px_104px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
                <div>
                  <div className="text-ink truncate">{row.bot_name || row.bot_id}</div>
                  <div className="text-slate-500 text-xs font-mono truncate">{row.llm_provider || "unknown"}</div>
                </div>
                <div className="text-slate-700">{row.outcome_count || 0}</div>
                <div className="text-emerald-600">{row.profitable_count || 0}</div>
                <div className="text-slate-700">{pct(row.win_rate)}</div>
                <div className={(row.total_net_after_llm_cost || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}>
                  {signedMoney(row.total_net_after_llm_cost, 2)}
                </div>
                <div className="text-rose-600">{row.risk_rejected_count || 0}</div>
                <div className="text-slate-700">{money(row.total_llm_estimated_cost_usd, 4)}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="px-5 py-4 overflow-x-auto">
        <div className="min-w-[960px]">
          <div className="grid grid-cols-[120px_1.2fr_90px_100px_100px_100px_1fr] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Observed</div>
            <div>Bot</div>
            <div>Action</div>
            <div>Status</div>
            <div>Position</div>
            <div>Net</div>
            <div>Ticker</div>
          </div>
          {recentRows.length === 0 ? (
            <div className="py-5 text-sm text-slate-500">No recent outcomes for this horizon.</div>
          ) : (
            recentRows.slice(0, 12).map((row) => (
              <div key={row.id} className="grid grid-cols-[120px_1.2fr_90px_100px_100px_100px_1fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
                <div className="text-slate-500 text-xs">
                  {row.observed_at ? new Date(row.observed_at).toLocaleString() : "n/a"}
                </div>
                <div>
                  <div className="text-ink truncate">{row.bot_name || row.bot_id}</div>
                  <div className="text-slate-500 text-xs font-mono">{row.llm_provider}</div>
                </div>
                <div className="text-slate-700">{row.action}</div>
                <div className={outcomeStatusClass(row.outcome_status)}>{row.outcome_status}</div>
                <div className={(row.position_pnl || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}>
                  {signedMoney(row.position_pnl, 2)}
                </div>
                <div className={(row.net_after_llm_cost || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}>
                  {signedMoney(row.net_after_llm_cost, 2)}
                </div>
                <div className="text-slate-700 truncate">
                  {row.ticker || "n/a"} {row.filled_quantity ? `${row.filled_quantity} filled` : ""}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function replayResearchExportRows(data) {
  return (data?.standings?.bot_provider || []).map((row) => flattenForCsv(row));
}

function ReplayResearchPanel({ data, loading, error }) {
  if (loading) {
    return <Skeleton className="h-[520px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
        {error}
      </section>
    );
  }
  if (!data) return null;

  if (!data.available) {
    return (
      <section className="bg-amber-50 border border-amber-200 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-amber-800">Six-Month Replay Research</h2>
        <div className="mt-2 text-sm text-amber-700">{data.error || "Replay research artifacts are not available."}</div>
        {data.expected_command && (
          <div className="mt-3 rounded-md bg-white/70 px-3 py-2 text-xs font-mono text-amber-800 break-all">
            {data.expected_command}
          </div>
        )}
      </section>
    );
  }

  const overall = data.overall || {};
  const botRows = data.standings?.bot_provider || [];
  const providerRows = data.standings?.provider || [];
  const modelRows = Object.entries(data.model_suite_summary || {});
  const cost = data.cost_summary || {};
  const exportRows = replayResearchExportRows(data);

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-1">
            <h2 className="text-sm font-semibold text-ink">Six-Month Replay Research</h2>
            <InfoTooltip label="What is this?">
              Summary of the six-month replay dataset, standings, labels, and exploratory ML model results.
            </InfoTooltip>
          </div>
          <div className="mt-1 text-slate-500 text-xs font-mono">
            version {data.version || "n/a"} | benchmark {data.benchmark || "SPY"} | generated {formatDateTime(data.generated_at)}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end">
          <ExportButton onClick={() => downloadJson("replay-research", data)}>
            JSON
          </ExportButton>
          <ExportButton
            disabled={exportRows.length === 0}
            onClick={() => downloadCsv("replay-research-bot-standings", exportRows)}
          >
            Standings CSV
          </ExportButton>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 p-5 border-b border-border md:grid-cols-5">
        <Metric label="Decisions" value={number(overall.decision_count)} sub={`${number(overall.trade_count)} trades`} />
        <Metric label="1d Direction" value={rate(overall.directional_accuracy_1d)} sub={`${number(overall.labeled_trade_count_1d)} labeled trades`} />
        <Metric label="Beat SPY" value={rate(overall.beat_benchmark_rate_1d)} sub="relative 1d target" />
        <Metric label="Intent PnL" value={signedMoney(overall.intent_mark_pnl_1d, 0)} sub="no-orders mark PnL" />
        <Metric
          label="Replay Cost"
          value={cost.available ? money(cost.total_estimated_llm_cost_usd, 4) : "n/a"}
          sub={cost.available ? `${number(cost.recorded_cost_count)} rows` : "not captured for this run"}
        />
      </div>

      {!cost.available && (
        <div className="mx-5 mt-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {cost.reason || "Exact replay model cost was not captured for this report."}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 p-5 border-b border-border lg:grid-cols-2">
        <div>
          <h3 className="text-xs font-mono uppercase tracking-widest text-slate-500">What Looks Good</h3>
          <div className="mt-3 space-y-2 text-sm text-slate-700">
            {(data.lessons?.positive || []).length === 0 ? (
              <div>No strong positive pattern is decision-grade yet.</div>
            ) : (
              data.lessons.positive.slice(0, 5).map((item) => <div key={item}>{item}</div>)
            )}
          </div>
        </div>
        <div>
          <h3 className="text-xs font-mono uppercase tracking-widest text-slate-500">What Looks Risky</h3>
          <div className="mt-3 space-y-2 text-sm text-slate-700">
            {(data.lessons?.negative || []).length === 0 ? (
              <div>No major risk pattern was detected.</div>
            ) : (
              data.lessons.negative.slice(0, 5).map((item) => <div key={item}>{item}</div>)
            )}
          </div>
        </div>
      </div>

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[920px]">
          <div className="grid grid-cols-[1.3fr_90px_90px_100px_100px_120px_110px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Bot / Provider</div>
            <div>Decisions</div>
            <div>Trades</div>
            <div>1d Dir</div>
            <div>Beat SPY</div>
            <div>Intent PnL</div>
            <div>Risk Blocks</div>
          </div>
          {botRows.length === 0 ? (
            <div className="py-5 text-sm text-slate-500">No replay standings available.</div>
          ) : (
            botRows.map((row) => (
              <div key={row.label} className="grid grid-cols-[1.3fr_90px_90px_100px_100px_120px_110px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
                <div className="text-ink truncate">{row.label}</div>
                <div className="text-slate-700">{number(row.decision_count)}</div>
                <div className="text-slate-700">{number(row.trade_count)}</div>
                <div className="text-slate-700">{rate(row.directional_accuracy_1d)}</div>
                <div className="text-slate-700">{rate(row.beat_benchmark_rate_1d)}</div>
                <div className={(row.intent_mark_pnl_1d || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}>
                  {signedMoney(row.intent_mark_pnl_1d, 0)}
                </div>
                <div className="text-rose-600">{number(row.risk_blocked_count)}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[700px]">
          <div className="grid grid-cols-[1fr_100px_100px_120px_120px] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>Provider</div>
            <div>Trades</div>
            <div>1d Dir</div>
            <div>Beat SPY</div>
            <div>Intent PnL</div>
          </div>
          {providerRows.map((row) => (
            <div key={row.label} className="grid grid-cols-[1fr_100px_100px_120px_120px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
              <div className="text-ink truncate">{row.label}</div>
              <div className="text-slate-700">{number(row.trade_count)}</div>
              <div className="text-slate-700">{rate(row.directional_accuracy_1d)}</div>
              <div className="text-slate-700">{rate(row.beat_benchmark_rate_1d)}</div>
              <div className={(row.intent_mark_pnl_1d || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}>
                {signedMoney(row.intent_mark_pnl_1d, 0)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="px-5 py-4 border-b border-border overflow-x-auto">
        <div className="min-w-[860px]">
          <div className="grid grid-cols-[1.4fr_90px_1fr_1fr] gap-3 py-2 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
            <div>ML Target</div>
            <div>Rows</div>
            <div>Best Accuracy</div>
            <div>Best F1</div>
          </div>
          {modelRows.length === 0 ? (
            <div className="py-5 text-sm text-slate-500">No model suite summary available.</div>
          ) : (
            modelRows.map(([target, row]) => (
              <div key={target} className="grid grid-cols-[1.4fr_90px_1fr_1fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
                <div className="text-ink font-mono text-xs truncate">{target}</div>
                <div className="text-slate-700">{number(row.usable_rows)}</div>
                <div className="text-slate-700">{row.best_model_by_test_accuracy || "n/a"}</div>
                <div className="text-slate-700">{row.best_model_by_test_f1 || "n/a"}</div>
              </div>
            ))
          )}
        </div>
      </div>

      {data.markdown_report && (
        <details className="px-5 py-4">
          <summary className="cursor-pointer text-sm font-semibold text-ink">Markdown Report</summary>
          <pre className="mt-3 max-h-[360px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
            {data.markdown_report}
          </pre>
        </details>
      )}
    </section>
  );
}

function fixtureTimeRange(row) {
  if (!row?.start_time && !row?.end_time) return "n/a";
  const start = row.start_time ? new Date(row.start_time).toLocaleDateString() : "n/a";
  const end = row.end_time ? new Date(row.end_time).toLocaleDateString() : "n/a";
  return start === end ? start : `${start} - ${end}`;
}

function ReplayFixtureLibrary({ data, loading, error }) {
  const [copied, setCopied] = useState(null);
  if (loading) {
    return <Skeleton className="h-[280px] rounded-lg" />;
  }
  if (error) {
    return (
      <section className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
        {error}
      </section>
    );
  }

  const fixtures = data?.fixtures || [];

  async function copyCommand(key, command) {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1400);
    } catch {
      setCopied("failed");
      window.setTimeout(() => setCopied(null), 1400);
    }
  }

  return (
    <section className="bg-panel border border-border rounded-lg">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Replay Fixture Library</h2>
          <div className="mt-1 text-slate-500 text-xs font-mono">
            {fixtures.length} scenarios | {data?.recommended_bots?.join(", ") || "analyst, bear, macro"}
          </div>
        </div>
        <ExportButton disabled={!data} onClick={() => downloadJson("replay-fixtures", data)}>
          JSON
        </ExportButton>
      </div>

      <div className="divide-y divide-border">
        {fixtures.length === 0 ? (
          <div className="px-5 py-5 text-sm text-slate-500">No bundled replay fixtures found.</div>
        ) : (
          fixtures.map((row) => (
            <div key={row.file_name} className="px-5 py-4">
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_180px_1fr]">
                <div>
                  <div className="text-sm font-semibold text-ink">{row.name}</div>
                  <div className="mt-1 text-xs text-slate-500">{row.description || row.file_name}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-700">{row.event_count} events</span>
                    <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-700">{fixtureTimeRange(row)}</span>
                    {(row.tickers || []).slice(0, 8).map((ticker) => (
                      <span key={ticker} className="rounded-md bg-blue-50 px-2 py-1 text-blue-700">
                        {ticker}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-xs text-slate-600">
                  {(row.expected_notes || []).slice(0, 3).map((note) => (
                    <div key={note} className="mb-2 border-l-2 border-border pl-3">
                      {note}
                    </div>
                  ))}
                </div>
                <div className="min-w-0">
                  <div className="rounded-md bg-slate-950 p-3 text-xs font-mono text-slate-100">
                    <div className="truncate">{row.matrix_command}</div>
                  </div>
                  <div className="mt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={() => copyCommand(row.file_name, row.matrix_command)}
                      className="rounded-md border border-border px-3 py-2 text-xs font-mono text-slate-700 hover:bg-slate-100"
                    >
                      {copied === row.file_name ? "Copied" : copied === "failed" ? "Copy Failed" : "Copy Matrix"}
                    </button>
                  </div>
                </div>
              </div>
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
  const [liveReport, setLiveReport] = useState(null);
  const [liveReportLoading, setLiveReportLoading] = useState(false);
  const [liveReportError, setLiveReportError] = useState(null);
  const [outcomeSummary, setOutcomeSummary] = useState(null);
  const [recentOutcomes, setRecentOutcomes] = useState(null);
  const [outcomeHorizon, setOutcomeHorizon] = useState("1h");
  const [outcomeLoading, setOutcomeLoading] = useState(false);
  const [outcomeError, setOutcomeError] = useState(null);
  const [riskRejections, setRiskRejections] = useState(null);
  const [automationStatus, setAutomationStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [replayResearch, setReplayResearch] = useState(null);
  const [replayResearchLoading, setReplayResearchLoading] = useState(false);
  const [replayResearchError, setReplayResearchError] = useState(null);
  const [replayFixtures, setReplayFixtures] = useState(null);
  const [fixtureLoading, setFixtureLoading] = useState(false);
  const [fixtureError, setFixtureError] = useState(null);
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
        setLiveReportLoading(true);
        setOutcomeLoading(true);
        setFixtureLoading(true);
        setReplayResearchLoading(true);
        const [
          summaryData,
          liveReportData,
          outcomeData,
          recentOutcomeData,
          fixtureData,
          replayResearchData,
          runData,
          riskData,
          automationData,
        ] = await Promise.all([
          getEvaluationSummary(),
          getLiveEvaluationReport(),
          getOutcomeSummary({ horizon: "1h" }),
          getRecentOutcomes({ horizon: "1h", limit: 100 }),
          getReplayFixtures(),
          getReplayResearch(),
          getReplayRuns(),
          getRiskRejections(100),
          getEvaluationSchedulerStatus(),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setLiveReport(liveReportData);
          setOutcomeSummary(outcomeData);
          setRecentOutcomes(recentOutcomeData);
          setReplayFixtures(fixtureData);
          setReplayResearch(replayResearchData);
          setRuns(runData);
          setRiskRejections(riskData);
          setAutomationStatus(automationData);
          setError(null);
          setLiveReportError(null);
          setOutcomeError(null);
          setFixtureError(null);
          setReplayResearchError(null);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err.message || "Failed to load evaluation data";
          setError(message);
          setLiveReportError(message);
          setReplayResearchError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setLiveReportLoading(false);
          setOutcomeLoading(false);
          setFixtureLoading(false);
          setReplayResearchLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const totals = summary?.totals;
  const providerRows = summary?.provider_comparison || [];

  async function loadOutcomes(nextHorizon) {
    try {
      setOutcomeHorizon(nextHorizon);
      setOutcomeLoading(true);
      setOutcomeError(null);
      const [summaryData, recentData] = await Promise.all([
        getOutcomeSummary({ horizon: nextHorizon }),
        getRecentOutcomes({ horizon: nextHorizon, limit: 100 }),
      ]);
      setOutcomeSummary(summaryData);
      setRecentOutcomes(recentData);
    } catch (err) {
      setOutcomeSummary(null);
      setRecentOutcomes(null);
      setOutcomeError(err.message || "Failed to load outcome data");
    } finally {
      setOutcomeLoading(false);
    }
  }

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
          <EvaluationAutomationPanel status={automationStatus} />

          <LiveEvaluationPanel
            data={liveReport}
            loading={liveReportLoading}
            error={liveReportError}
          />

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

          <OutcomePanel
            summary={outcomeSummary}
            recent={recentOutcomes}
            horizon={outcomeHorizon}
            loading={outcomeLoading}
            error={outcomeError}
            onHorizonChange={loadOutcomes}
          />

          <ReplayResearchPanel
            data={replayResearch}
            loading={replayResearchLoading}
            error={replayResearchError}
          />

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

          <ReplayFixtureLibrary
            data={replayFixtures}
            loading={fixtureLoading}
            error={fixtureError}
          />

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
