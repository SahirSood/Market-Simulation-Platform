import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAllBotReasoning } from "../../hooks/useAllBotReasoning";
import { useBots } from "../../hooks/useBots";
import { formatDollar, providerLabel, shortName, startingCashFor } from "../../lib/botUtils";
import InfoTooltip from "../ui/InfoTooltip";
import TimeRangeToggle from "./TimeRangeToggle";

const DEFAULT_STARTING_CASH = 100_000;
const VIEW_MODES = [
  { value: "all", label: "All 10" },
  { value: "claude", label: "Claude" },
  { value: "openai", label: "OpenAI" },
  { value: "bot", label: "Single Bot" },
];

const CLAUDE_COLORS = ["#2563EB", "#38BDF8", "#4F46E5", "#0891B2", "#16A34A"];
const OPENAI_COLORS = ["#F97316", "#EA580C", "#F59E0B", "#DC2626", "#A16207"];
const RANGE_MS = {
  "1H": 3600 * 1000,
  "6H": 6 * 3600 * 1000,
  "1D": 24 * 3600 * 1000,
  "7D": 7 * 24 * 3600 * 1000,
  "30D": 30 * 24 * 3600 * 1000,
  All: Infinity,
};
const LIVE_SAMPLE_MAX = 480;

function botColor(bot, index) {
  const palette = bot?.llm_provider === "claude" ? CLAUDE_COLORS : OPENAI_COLORS;
  return palette[index % palette.length];
}

function pct(value) {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function returnPct(value, startingCash = DEFAULT_STARTING_CASH) {
  const base = Number(startingCash || DEFAULT_STARTING_CASH);
  return ((Number(value || base) - base) / base) * 100;
}

function formatXLabel(isoTs, range) {
  const d = new Date(isoTs);
  if (range === "1H" || range === "6H" || range === "1D") {
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric" });
}

function cutoffForRange(range) {
  const span = RANGE_MS[range] ?? Infinity;
  return Number.isFinite(span) ? Date.now() - span : -Infinity;
}

function useLiveValueSamples(bots) {
  const [samples, setSamples] = useState(new Map());
  const botsKey = bots
    .map((bot) => `${bot.bot_id}:${bot.total_value ?? "na"}:${bot.position_count ?? 0}`)
    .join("|");

  useEffect(() => {
    if (!bots.length) return;
    const timestamp = new Date().toISOString();
    setSamples((prev) => {
      const next = new Map(prev);
      bots.forEach((bot) => {
        if (bot.total_value == null) return;
        const prior = next.get(bot.bot_id) || [];
        const updated = [...prior, { timestamp, value: Number(bot.total_value) }].slice(-LIVE_SAMPLE_MAX);
        next.set(bot.bot_id, updated);
      });
      return next;
    });
  }, [bots.length, botsKey]);

  return samples;
}

function buildBotSeries(bot, reasoningMap, liveSamples, color, nowIso) {
  const points = reasoningMap.get(bot.bot_id) || [];
  const samples = liveSamples.get(bot.bot_id) || [];
  const startingCash = startingCashFor(bot, DEFAULT_STARTING_CASH);
  const currentPoint = bot.total_value == null ? [] : [{ timestamp: nowIso, value: bot.total_value }];
  return {
    id: bot.bot_id,
    label: `${shortName(bot.name)} ${providerLabel(bot)}`,
    provider: bot.llm_provider,
    color,
    startingCash,
    currentValue: Number(bot.total_value ?? startingCash),
    points: [...points, ...samples, ...currentPoint].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)),
  };
}

function buildChartData(series, range) {
  const cutoff = cutoffForRange(range);
  const filtered = series.map((item) => ({
    ...item,
    points: item.points.filter((point) => new Date(point.timestamp).getTime() >= cutoff),
  }));
  const timestamps = [...new Set(filtered.flatMap((item) => item.points.map((point) => point.timestamp)))].sort();

  if (!timestamps.length) return [];

  const maps = Object.fromEntries(
    filtered.map((item) => [item.id, Object.fromEntries(item.points.map((point) => [point.timestamp, point.value]))])
  );
  const lastValues = Object.fromEntries(filtered.map((item) => [item.id, item.startingCash]));

  return timestamps.map((timestamp) => {
    const row = { time: formatXLabel(timestamp, range), rawTs: timestamp };
    filtered.forEach((item) => {
      if (maps[item.id][timestamp] !== undefined) lastValues[item.id] = maps[item.id][timestamp];
      row[item.id] = Number(returnPct(lastValues[item.id], item.startingCash).toFixed(2));
    });
    return row;
  });
}

function averageReturn(bots) {
  if (!bots.length) return 0;
  return bots.reduce((sum, bot) => sum + returnPct(bot.total_value, startingCashFor(bot)), 0) / bots.length;
}

function averagePnl(bots) {
  if (!bots.length) return 0;
  return bots.reduce((sum, bot) => {
    const base = startingCashFor(bot, DEFAULT_STARTING_CASH);
    return sum + (Number(bot.total_value ?? base) - base);
  }, 0) / bots.length;
}

function leaderFor(bots) {
  if (!bots.length) return null;
  return [...bots].sort(
    (a, b) => returnPct(b.total_value, startingCashFor(b)) - returnPct(a.total_value, startingCashFor(a))
  )[0];
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload
    .filter((item) => item.value != null)
    .sort((a, b) => Number(b.value) - Number(a.value));

  return (
    <div className="max-w-[280px] rounded-2xl border border-border bg-white p-3 text-xs shadow-xl shadow-slate-200/80">
      <p className="mb-2 font-mono text-slate-500">{label}</p>
      <div className="space-y-1">
        {rows.slice(0, 10).map((item) => (
          <div key={item.dataKey} className="flex items-center justify-between gap-4 font-mono">
            <span className="truncate" style={{ color: item.color }}>
              {item.name}
            </span>
            <span className={item.value >= 0 ? "text-emerald-600" : "text-rose-600"}>
              {pct(Number(item.value))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ModeButton({ mode, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "min-w-[68px] flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors sm:flex-none sm:min-w-[76px]",
        active ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
      ].join(" ")}
    >
      {mode.label}
    </button>
  );
}

function TinyStat({ label, value, sub, color = "#0F172A" }) {
  return (
    <div className="min-w-0 rounded-2xl border border-border bg-white px-4 py-3 shadow-sm shadow-slate-200/50">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className="mt-1 truncate font-mono text-lg font-bold" style={{ color }}>
        {value}
      </div>
      {sub ? <div className="mt-0.5 truncate text-xs text-slate-500">{sub}</div> : null}
    </div>
  );
}

function TeamCard({ team, bots, avgPnl, avgReturnValue, color, bgClass, align = "left" }) {
  const isRight = align === "right";
  const signClass = avgPnl >= 0 ? "text-emerald-600" : "text-rose-600";

  return (
    <div className={`rounded-xl border border-border ${bgClass} px-4 py-4 shadow-sm sm:rounded-[24px] sm:px-5`}>
      <div className={`flex items-center gap-2 ${isRight ? "justify-end" : ""}`}>
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{team} average</div>
      </div>
      <div className={`mt-2 font-mono text-2xl font-black tracking-tight ${signClass}`}>
        {avgPnl >= 0 ? "+" : "-"}
        {formatDollar(Math.abs(avgPnl))}
      </div>
      <div className="mt-1 text-sm font-medium text-slate-700">{pct(avgReturnValue)} across {bots.length} bots</div>
    </div>
  );
}

function teamValue(pnlValue, ret) {
  const sign = pnlValue >= 0 ? "+" : "-";
  return `${sign}${formatDollar(Math.abs(pnlValue))} (${pct(ret)})`;
}

function Legend({ series }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {series.map((item) => {
        const value = returnPct(item.currentValue, item.startingCash);
        return (
          <div key={item.id} className="flex min-w-0 items-center justify-between gap-2 rounded-full border border-border bg-white px-3 py-2 shadow-sm">
            <div className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="truncate text-xs font-medium text-slate-700">{item.label}</span>
            </div>
            <span className={`shrink-0 font-mono text-xs ${value >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {pct(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ComparisonChart() {
  const [viewMode, setViewMode] = useState("all");
  const [timeRange, setTimeRange] = useState("1D");
  const [selectedBotId, setSelectedBotId] = useState("");

  const { claudeBots, gptBots, loading: botsLoading } = useBots();
  const allBots = useMemo(() => [...claudeBots, ...gptBots], [claudeBots, gptBots]);
  const allBotIds = useMemo(() => allBots.map((bot) => bot.bot_id), [allBots]);
  const { reasoningMap, loading: reasoningLoading } = useAllBotReasoning(allBotIds);
  const liveSamples = useLiveValueSamples(allBots);

  useEffect(() => {
    if (!selectedBotId && allBots.length) setSelectedBotId(allBots[0].bot_id);
  }, [allBots, selectedBotId]);

  const visibleBots = useMemo(() => {
    if (viewMode === "claude") return claudeBots;
    if (viewMode === "openai") return gptBots;
    if (viewMode === "bot") return allBots.filter((bot) => bot.bot_id === selectedBotId);
    return allBots;
  }, [allBots, claudeBots, gptBots, selectedBotId, viewMode]);

  const nowIso = useMemo(() => new Date().toISOString(), [reasoningMap, allBots]);
  const series = useMemo(
    () => visibleBots.map((bot, index) => buildBotSeries(bot, reasoningMap, liveSamples, botColor(bot, index), nowIso)),
    [nowIso, reasoningMap, liveSamples, visibleBots]
  );
  const chartData = useMemo(() => buildChartData(series, timeRange), [series, timeRange]);

  const claudeAvg = averageReturn(claudeBots);
  const openaiAvg = averageReturn(gptBots);
  const claudeAvgPnl = averagePnl(claudeBots);
  const openaiAvgPnl = averagePnl(gptBots);
  const spread = claudeAvgPnl - openaiAvgPnl;
  const leader = leaderFor(allBots);
  const leadingTeam = Math.abs(spread) < 1 ? "Even" : spread > 0 ? "Claude" : "OpenAI";

  if (botsLoading) {
    return (
      <div className="rounded-[28px] border border-border bg-white p-6 shadow-sm">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-56 rounded-full bg-slate-200" />
          <div className="h-[340px] rounded-[24px] bg-slate-100" />
        </div>
      </div>
    );
  }

  return (
    <section className="space-y-5 rounded-xl border border-border bg-white p-4 shadow-xl shadow-slate-200/70 sm:rounded-[32px] sm:p-5 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            Live AI market experiment
          </div>
          <div className="mt-3 flex items-start gap-2">
            <h1 className="text-2xl font-black tracking-tight text-ink sm:text-3xl md:text-4xl">
              Claude vs OpenAI, trading live
            </h1>
            <InfoTooltip label="Is this read-only?">
              Yes. Public visitors can inspect the arena, but only the backend scheduler can advance agents and submit
              simulated orders through risk checks.
            </InfoTooltip>
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Ten matched bot personalities compete on the same market feed. Visitors can watch returns, trades, risk
            outcomes, short public rationales, and SEC evidence without controlling the simulation.
          </p>
        </div>
        <TimeRangeToggle value={timeRange} onChange={setTimeRange} />
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_auto_1fr] lg:items-stretch">
        <TeamCard
          team="Claude"
          bots={claudeBots}
          avgPnl={claudeAvgPnl}
          avgReturnValue={claudeAvg}
          color="#2563EB"
          bgClass="bg-soft-blue"
        />
        <div className="flex min-h-[112px] items-center justify-center rounded-xl border border-border bg-white px-6 text-center shadow-sm sm:rounded-[24px]">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Current leader</div>
            <div className="mt-1 text-xl font-black text-ink">{leadingTeam}</div>
            <div className="mt-1 font-mono text-xs text-slate-500">
              {Math.abs(spread) < 1 ? "within $1 avg" : `${formatDollar(Math.abs(spread))} avg spread`}
            </div>
          </div>
        </div>
        <TeamCard
          team="OpenAI"
          bots={gptBots}
          avgPnl={openaiAvgPnl}
          avgReturnValue={openaiAvg}
          color="#F97316"
          bgClass="bg-soft-orange"
          align="right"
        />
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex w-full flex-wrap gap-1 rounded-xl border border-border bg-white p-1 shadow-sm sm:w-auto sm:rounded-full">
          {VIEW_MODES.map((mode) => (
            <ModeButton
              key={mode.value}
              mode={mode}
              active={viewMode === mode.value}
              onClick={() => setViewMode(mode.value)}
            />
          ))}
        </div>

        {viewMode === "bot" ? (
          <select
            value={selectedBotId}
            onChange={(event) => setSelectedBotId(event.target.value)}
            className="min-h-[40px] w-full rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm outline-none transition-colors focus:border-claude sm:w-auto sm:rounded-full"
          >
            {allBots.map((bot) => (
              <option key={bot.bot_id} value={bot.bot_id}>
                {shortName(bot.name)} - {providerLabel(bot)}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <TinyStat label="View" value={VIEW_MODES.find((mode) => mode.value === viewMode)?.label || "All 10"} sub={timeRange} />
        <TinyStat label="Visible Lines" value={String(series.length)} sub="return traces" color="#334155" />
        <TinyStat
          label="Top Bot"
          value={leader ? shortName(leader.name) : "n/a"}
          sub={
            leader
              ? `${providerLabel(leader)} ${pct(returnPct(leader.total_value, startingCashFor(leader)))} (${formatDollar(leader.total_value)})`
              : null
          }
          color={leader?.llm_provider === "claude" ? "#2563EB" : "#F97316"}
        />
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-slate-50 p-2 sm:rounded-[26px] sm:p-3">
        {chartData.length === 0 ? (
          <div className="flex h-[340px] items-center justify-center">
            <p className="font-mono text-sm text-slate-500">
              {reasoningLoading ? "Loading chart data..." : "Waiting for first decisions..."}
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="#CBD5E1"
                tick={{ fill: "#64748B", fontFamily: "JetBrains Mono", fontSize: 11 }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="#CBD5E1"
                tick={{ fill: "#64748B", fontFamily: "JetBrains Mono", fontSize: 11 }}
                tickFormatter={(value) => `${value}%`}
                tickLine={false}
                axisLine={false}
                width={58}
              />
              <ReferenceLine y={0} stroke="#94A3B8" strokeDasharray="4 4" />
              <Tooltip content={<CustomTooltip />} />
              {series.map((item) => (
                <Line
                  key={item.id}
                  dataKey={item.id}
                  name={item.label}
                  stroke={item.color}
                  strokeWidth={viewMode === "bot" ? 3 : 2.25}
                  strokeOpacity={viewMode === "all" ? 0.72 : 0.95}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <Legend series={series} />
      <div className="sr-only">{teamValue(claudeAvgPnl, claudeAvg)} vs {teamValue(openaiAvgPnl, openaiAvg)}</div>
    </section>
  );
}
