import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  Tooltip,
} from "recharts";

import { useBots } from "../../hooks/useBots";
import { useAllBotReasoning } from "../../hooks/useAllBotReasoning";
import { shortName, providerLabel, formatDollar, startingCashFor } from "../../lib/botUtils";

import TimeRangeToggle from "./TimeRangeToggle";

const DEFAULT_STARTING_CASH = 100_000;
const VIEW_MODES = [
  { value: "all", label: "All 10" },
  { value: "claude", label: "Claude" },
  { value: "openai", label: "OpenAI" },
  { value: "bot", label: "Single Bot" },
];

const CLAUDE_COLORS = ["#60A5FA", "#2563EB", "#38BDF8", "#818CF8", "#14B8A6"];
const OPENAI_COLORS = ["#FB923C", "#F97316", "#F59E0B", "#EF4444", "#84CC16"];
const RANGE_MS = {
  "1H": 3600 * 1000,
  "6H": 6 * 3600 * 1000,
  "1D": 24 * 3600 * 1000,
  "7D": 7 * 24 * 3600 * 1000,
  "30D": 30 * 24 * 3600 * 1000,
  All: Infinity,
};

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

function buildBotSeries(bot, reasoningMap, color, nowIso) {
  const points = reasoningMap.get(bot.bot_id) || [];
  const startingCash = startingCashFor(bot, DEFAULT_STARTING_CASH);
  const currentPoint = bot.total_value == null ? [] : [{ timestamp: nowIso, value: bot.total_value }];
  return {
    id: bot.bot_id,
    label: `${shortName(bot.name)} ${providerLabel(bot)}`,
    provider: bot.llm_provider,
    color,
    startingCash,
    currentValue: Number(bot.total_value ?? startingCash),
    points: [...points, ...currentPoint].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)),
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
    <div className="max-w-[280px] rounded-lg border border-border bg-panel p-3 text-xs shadow-lg">
      <p className="mb-2 font-mono text-[#64748B]">{label}</p>
      <div className="space-y-1">
        {rows.slice(0, 10).map((item) => (
          <div key={item.dataKey} className="flex items-center justify-between gap-4 font-mono">
            <span className="truncate" style={{ color: item.color }}>
              {item.name}
            </span>
            <span className={item.value >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}>
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
        "min-w-[76px] rounded-md px-3 py-1.5 text-xs font-mono font-semibold transition-colors",
        active ? "bg-[#3B82F6] text-white" : "text-[#64748B] hover:bg-[#16161F] hover:text-[#F1F5F9]",
      ].join(" ")}
    >
      {mode.label}
    </button>
  );
}

function StatCard({ label, value, sub, color = "#F1F5F9" }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-bg px-4 py-3">
      <div className="text-[10px] font-mono uppercase tracking-widest text-[#64748B]">{label}</div>
      <div className="mt-1 truncate font-mono text-lg font-bold" style={{ color }}>
        {value}
      </div>
      {sub ? <div className="mt-0.5 truncate text-xs text-[#64748B]">{sub}</div> : null}
    </div>
  );
}

function teamValue(pnl, ret) {
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}${formatDollar(Math.abs(pnl))} (${pct(ret)})`;
}

function Legend({ series }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {series.map((item) => {
        const value = returnPct(item.currentValue, item.startingCash);
        return (
          <div key={item.id} className="flex min-w-0 items-center justify-between gap-2 rounded-md bg-bg px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="truncate text-xs text-[#CBD5E1]">{item.label}</span>
            </div>
            <span className={`shrink-0 font-mono text-xs ${value >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
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
    () => visibleBots.map((bot, index) => buildBotSeries(bot, reasoningMap, botColor(bot, index), nowIso)),
    [nowIso, reasoningMap, visibleBots]
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
      <div className="rounded-xl border border-border bg-panel p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-5 w-48 rounded bg-[#1E1E2E]" />
          <div className="h-[340px] rounded-lg bg-[#1E1E2E]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 rounded-xl border border-border bg-panel p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#F1F5F9]">Claude vs OpenAI Live Battle</h1>
          <p className="mt-1 text-sm text-[#64748B]">
            {allBots.length} live traders, matched personalities, live decisions, live returns.
          </p>
        </div>
        <TimeRangeToggle value={timeRange} onChange={setTimeRange} />
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_auto_1fr] lg:items-stretch">
        <div className="rounded-lg border border-[#2563EB]/40 bg-[#0B1220] px-5 py-4">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#60A5FA]">Claude Average</div>
          <div className="mt-2 font-mono text-2xl font-bold text-[#BFDBFE]">
            {teamValue(claudeAvgPnl, claudeAvg)}
          </div>
          <div className="mt-1 text-xs text-[#64748B]">{claudeBots.length} bots</div>
        </div>
        <div className="flex min-h-[92px] items-center justify-center rounded-lg border border-border bg-bg px-5 text-center">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#64748B]">Leader</div>
            <div className="mt-1 text-lg font-semibold text-[#F1F5F9]">{leadingTeam}</div>
            <div className="mt-0.5 font-mono text-xs text-[#64748B]">
              {Math.abs(spread) < 1 ? "within $1 avg" : `${formatDollar(Math.abs(spread))} avg spread`}
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-[#F97316]/40 bg-[#1F1308] px-5 py-4 lg:text-right">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#FB923C]">OpenAI Average</div>
          <div className="mt-2 font-mono text-2xl font-bold text-[#FED7AA]">
            {teamValue(openaiAvgPnl, openaiAvg)}
          </div>
          <div className="mt-1 text-xs text-[#64748B]">{gptBots.length} bots</div>
        </div>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-1 rounded-lg border border-border bg-bg p-1">
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
            className="min-h-[36px] rounded-lg border border-border bg-bg px-3 py-2 text-sm font-mono text-[#F1F5F9] outline-none"
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
        <StatCard label="View" value={VIEW_MODES.find((mode) => mode.value === viewMode)?.label || "All 10"} sub={timeRange} />
        <StatCard label="Lines" value={String(series.length)} sub="visible returns" color="#CBD5E1" />
        <StatCard
          label="Current Leader"
          value={leader ? shortName(leader.name) : "n/a"}
          sub={leader ? `${providerLabel(leader)} ${pct(returnPct(leader.total_value, startingCashFor(leader)))} (${formatDollar(leader.total_value)})` : null}
          color={leader?.llm_provider === "claude" ? "#60A5FA" : "#FB923C"}
        />
      </div>

      {chartData.length === 0 ? (
        <div className="flex h-[340px] items-center justify-center">
          <p className="font-mono text-sm text-[#64748B]">
            {reasoningLoading ? "Loading chart data..." : "Waiting for first decisions..."}
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="#334155"
              tick={{ fill: "#64748B", fontFamily: "JetBrains Mono", fontSize: 11 }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              stroke="#334155"
              tick={{ fill: "#64748B", fontFamily: "JetBrains Mono", fontSize: 11 }}
              tickFormatter={(value) => `${value}%`}
              tickLine={false}
              axisLine={false}
              width={58}
            />
            <ReferenceLine y={0} stroke="#334155" strokeDasharray="4 4" />
            <Tooltip content={<CustomTooltip />} />
            {series.map((item) => (
              <Line
                key={item.id}
                dataKey={item.id}
                name={item.label}
                stroke={item.color}
                strokeWidth={viewMode === "bot" ? 3 : 2}
                strokeOpacity={viewMode === "all" ? 0.72 : 0.95}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}

      <Legend series={series} />
    </div>
  );
}
