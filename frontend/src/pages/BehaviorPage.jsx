import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getBotBehavior,
  getBotBehaviorDetail,
  getEvidenceChunks,
} from "../api/endpoints";
import EvidenceDrawer from "../components/evaluation/EvidenceDrawer";
import Skeleton from "../components/ui/Skeleton";
import { downloadCsv, downloadJson, flattenForCsv } from "../lib/exportUtils";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
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

function timeLabel(value) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusColor(status) {
  if (status === "unsupported") return "text-[#EF4444]";
  if (status === "speculative" || status === "speculative_evidence_backed") return "text-[#F97316]";
  if (status === "evidence_backed") return "text-[#22C55E]";
  return "text-[#64748B]";
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

function ExportButton({ children, onClick, disabled = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "px-3 py-2 rounded-md border border-border text-xs font-mono transition-colors",
        disabled
          ? "text-[#475569] cursor-not-allowed"
          : "text-[#CBD5E1] hover:bg-[#111827]",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function BotButton({ bot, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "w-full text-left px-4 py-3 border-b border-border last:border-b-0 transition-colors",
        selected ? "bg-[#111827]" : "hover:bg-[#0F172A]",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[#F1F5F9] text-sm truncate">{bot.bot_name || bot.bot_id}</div>
          <div className="mt-1 text-[#64748B] text-xs font-mono capitalize">
            {bot.llm_provider || "unknown"} | {bot.decision_count} decisions
          </div>
        </div>
        <div className="text-right text-xs font-mono text-[#64748B] shrink-0">
          {pct(bot.citation_rate)}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] font-mono">
        <div className="text-[#22C55E]">B {bot.action_counts?.BUY || 0}</div>
        <div className="text-[#EF4444]">S {bot.action_counts?.SELL || 0}</div>
        <div className="text-[#64748B]">H {bot.action_counts?.HOLD || 0}</div>
      </div>
    </button>
  );
}

function ChartPanel({ title, children }) {
  return (
    <section className="bg-panel border border-border rounded-lg p-5">
      <h2 className="text-sm font-semibold text-[#F1F5F9]">{title}</h2>
      <div className="mt-4 h-[260px]">{children}</div>
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

function Timeline({ rows, onOpenEvidence }) {
  return (
    <section className="bg-panel border border-border rounded-lg overflow-x-auto">
      <div className="px-5 py-4 border-b border-border">
        <h2 className="text-sm font-semibold text-[#F1F5F9]">Decision Timeline</h2>
      </div>
      <div className="min-w-[1040px] px-5">
        <div className="grid grid-cols-[86px_150px_96px_88px_150px_118px_1fr] gap-3 py-3 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
          <div>Time</div>
          <div>Decision</div>
          <div>Conf</div>
          <div>Cites</div>
          <div>Status</div>
          <div>Value</div>
          <div>Reason</div>
        </div>
        {rows.length === 0 ? (
          <div className="py-5 text-sm text-[#64748B]">No decisions logged for this bot.</div>
        ) : (
          rows.map((row) => (
            <div
              key={row.id || `${row.timestamp}-${row.action}`}
              className="grid grid-cols-[86px_150px_96px_88px_150px_118px_1fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm"
            >
              <div className="font-mono text-[#64748B]">{timeLabel(row.timestamp)}</div>
              <div>
                <div className="text-[#CBD5E1]">
                  {row.action} {row.quantity || ""} {row.ticker || ""}
                </div>
                {row.risk_rejected && (
                  <div className="mt-1 text-[#EF4444] text-xs">risk rejected</div>
                )}
              </div>
              <div className="text-[#CBD5E1]">
                {row.confidence === null || row.confidence === undefined
                  ? "n/a"
                  : row.confidence.toFixed(2)}
              </div>
              <div>
                <EvidenceButton ids={row.evidence_ids} onOpen={onOpenEvidence} />
              </div>
              <div className={statusColor(row.evidence_status)}>
                {row.evidence_status.replaceAll("_", " ")}
              </div>
              <div className="font-mono text-[#CBD5E1]">{money(row.portfolio_value)}</div>
              <div className="text-[#CBD5E1] truncate">{row.reasoning}</div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export default function BehaviorPage() {
  const [summary, setSummary] = useState(null);
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
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
      setLoading(true);
      const data = await getBotBehavior();
      if (cancelled) return;
      if (!data) {
        setError("Failed to load bot behavior");
        setLoading(false);
        return;
      }
      setSummary(data);
      setSelectedBotId(data.bots?.[0]?.bot_id || null);
      setError(null);
      setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedBotId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    async function loadDetail() {
      setDetailLoading(true);
      const data = await getBotBehaviorDetail(selectedBotId);
      if (cancelled) return;
      if (!data) {
        setDetail(null);
        setError("Failed to load selected bot behavior");
      } else {
        setDetail(data);
        setError(null);
      }
      setDetailLoading(false);
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedBotId]);

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

  const bot = detail?.bot;
  const timeline = detail?.timeline || [];
  const actionData = useMemo(() => {
    const counts = bot?.action_counts || {};
    return [
      { action: "BUY", count: counts.BUY || 0 },
      { action: "SELL", count: counts.SELL || 0 },
      { action: "HOLD", count: counts.HOLD || 0 },
    ];
  }, [bot]);
  const chartData = useMemo(
    () =>
      timeline.map((row) => ({
        time: timeLabel(row.timestamp),
        confidence: row.confidence,
        portfolio_value: row.portfolio_value,
      })),
    [timeline],
  );
  const botRows = (summary?.bots || []).map((row) => flattenForCsv(row));
  const timelineRows = timeline.map((row) => flattenForCsv(row));

  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-[#F1F5F9] font-semibold text-lg">Bot Behavior</h1>
          <p className="text-[#64748B] text-sm mt-1">
            Action mix, confidence, citations, risk rejections, fills, and portfolio traces.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ExportButton
            disabled={loading || !summary}
            onClick={() => downloadJson("bot-behavior-summary", summary)}
          >
            JSON
          </ExportButton>
          <ExportButton
            disabled={loading || botRows.length === 0}
            onClick={() => downloadCsv("bot-behavior-bots", botRows)}
          >
            Bots CSV
          </ExportButton>
          <ExportButton
            disabled={detailLoading || timelineRows.length === 0}
            onClick={() => downloadCsv("bot-behavior-timeline", timelineRows)}
          >
            Timeline CSV
          </ExportButton>
        </div>
      </div>

      {error && (
        <div className="bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-5 py-3 text-sm text-[#EF4444]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-6">
          <Skeleton className="h-[520px] rounded-lg" />
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-[104px] rounded-lg" />
              ))}
            </div>
            <Skeleton className="h-[360px] rounded-lg" />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-6">
          <section className="bg-panel border border-border rounded-lg overflow-hidden self-start">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-[#F1F5F9]">Bots</h2>
              <div className="text-xs font-mono text-[#64748B]">
                {summary?.bot_count || 0}
              </div>
            </div>
            <div>
              {(summary?.bots || []).length === 0 ? (
                <div className="px-5 py-6 text-sm text-[#64748B]">
                  No bot decisions logged yet.
                </div>
              ) : (
                summary.bots.map((item) => (
                  <BotButton
                    key={item.bot_id}
                    bot={item}
                    selected={item.bot_id === selectedBotId}
                    onClick={() => setSelectedBotId(item.bot_id)}
                  />
                ))
              )}
            </div>
          </section>

          <div className="space-y-6">
            {detailLoading ? (
              <Skeleton className="h-[420px] rounded-lg" />
            ) : bot ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <Metric
                    label="Citation Rate"
                    value={pct(bot.citation_rate)}
                    sub={`${bot.citation_count} cited chunks`}
                  />
                  <Metric
                    label="Unsupported"
                    value={pct(bot.unsupported_trade_rate)}
                    sub={`${bot.evidence_status_counts?.unsupported || 0} unsupported trades`}
                  />
                  <Metric
                    label="Fill Rate"
                    value={pct(bot.fill_rate)}
                    sub={`${bot.filled_quantity || 0} shares filled`}
                  />
                  <Metric
                    label="Risk Rejects"
                    value={bot.risk_rejection_count || 0}
                    sub={`Value ${signedMoney(bot.portfolio?.value_change)}`}
                  />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <ChartPanel title="Action Mix">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={actionData} margin={{ top: 6, right: 4, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" vertical={false} />
                        <XAxis dataKey="action" stroke="#64748B" tickLine={false} />
                        <YAxis stroke="#64748B" allowDecimals={false} tickLine={false} />
                        <Tooltip
                          cursor={{ fill: "#0F172A" }}
                          contentStyle={{ background: "#111118", border: "1px solid #1E1E2E" }}
                        />
                        <Bar dataKey="count" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartPanel>

                  <ChartPanel title="Confidence">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" vertical={false} />
                        <XAxis dataKey="time" stroke="#64748B" tickLine={false} />
                        <YAxis stroke="#64748B" domain={[0, 1]} tickLine={false} />
                        <Tooltip contentStyle={{ background: "#111118", border: "1px solid #1E1E2E" }} />
                        <Line dataKey="confidence" stroke="#F97316" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </ChartPanel>

                  <ChartPanel title="Portfolio Value">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" vertical={false} />
                        <XAxis dataKey="time" stroke="#64748B" tickLine={false} />
                        <YAxis
                          stroke="#64748B"
                          tickFormatter={(value) => `$${Math.round(value / 1000)}k`}
                          tickLine={false}
                        />
                        <Tooltip
                          formatter={(value) => [money(value), "Value"]}
                          contentStyle={{ background: "#111118", border: "1px solid #1E1E2E" }}
                        />
                        <Line dataKey="portfolio_value" stroke="#22C55E" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </ChartPanel>
                </div>

                <Timeline rows={timeline} onOpenEvidence={openEvidence} />
              </>
            ) : (
              <section className="bg-panel border border-border rounded-lg px-5 py-6 text-sm text-[#64748B]">
                Select a bot to inspect behavior.
              </section>
            )}
          </div>
        </div>
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
