import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAllBotReasoning } from "../../hooks/useAllBotReasoning";
import { useBots } from "../../hooks/useBots";
import { getAgentActivity } from "../../api/endpoints";
import { formatDollar, providerLabel, shortName, startingCashFor } from "../../lib/botUtils";
import { holdCauseLabel } from "../../lib/holdCauses";
import { useWebSocket } from "../../hooks/useWebSocket";
import InfoTooltip from "../ui/InfoTooltip";
import TimeRangeToggle from "./TimeRangeToggle";

const DEFAULT_STARTING_CASH = 100_000;
const VIEW_MODES = [
  { value: "teams", label: "Teams" },
  { value: "all", label: "All Bots" },
  { value: "bot", label: "Single Bot" },
];

const CLAUDE_COLORS = ["#3157D5", "#5572D9", "#263D99", "#44738A", "#087A55"];
const OPENAI_COLORS = ["#B95818", "#D1743A", "#9A4818", "#BE3543", "#80622A"];
const RANGE_MS = {
  "1H": 3600 * 1000,
  "6H": 6 * 3600 * 1000,
  "1D": 24 * 3600 * 1000,
  "7D": 7 * 24 * 3600 * 1000,
  "30D": 30 * 24 * 3600 * 1000,
  All: Infinity,
};
const LIVE_SAMPLE_MAX = 480;
const CHART_EVENT_POLL_INTERVAL = 30_000;

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

function buildTeamSeries({ id, label, provider, color, items }) {
  if (!items.length) {
    return {
      id,
      label,
      provider,
      color,
      startingCash: 100,
      currentValue: 100,
      points: [],
    };
  }

  const timestamps = [...new Set(items.flatMap((item) => item.points.map((point) => point.timestamp)))].sort();
  const pointMaps = Object.fromEntries(
    items.map((item) => [item.id, Object.fromEntries(item.points.map((point) => [point.timestamp, point.value]))])
  );
  const lastReturns = Object.fromEntries(items.map((item) => [item.id, 0]));

  const points = timestamps.map((timestamp) => {
    items.forEach((item) => {
      if (pointMaps[item.id][timestamp] !== undefined) {
        lastReturns[item.id] = returnPct(pointMaps[item.id][timestamp], item.startingCash);
      }
    });
    const avgReturn = items.reduce((sum, item) => sum + lastReturns[item.id], 0) / items.length;
    return { timestamp, value: 100 + avgReturn };
  });

  return {
    id,
    label,
    provider,
    color,
    startingCash: 100,
    currentValue: points.length ? points[points.length - 1].value : 100,
    points,
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

function liveEventIdentity(event) {
  return String(
    event.id ||
      [
        event.timestamp,
        event.bot_id,
        event.type,
        event.action,
        event.ticker || "",
        event.quantity || "",
      ].join("-")
  );
}

function activityToChartEvent(row) {
  if (!row?.bot_id || !row.timestamp) return null;
  const metadata = row.metadata && typeof row.metadata === "object" ? row.metadata : {};
  const base = {
    id: `activity-${row.id}`,
    decision_id: row.decision_id,
    bot_id: row.bot_id,
    bot_name: row.bot_name,
    llm_provider: row.llm_provider,
    timestamp: row.timestamp,
    reasoning: row.summary || "",
  };

  if (row.event_type === "decision" && row.stage === "decision") {
    return {
      ...base,
      type: "decision",
      action: "HOLD",
      ticker: null,
      quantity: null,
      fill_count: 0,
      hold_cause: metadata.hold_cause || null,
    };
  }

  if (row.event_type === "execution" && row.stage === "order_submit") {
    const action = String(metadata.action || "").toUpperCase();
    if (action !== "BUY" && action !== "SELL") return null;
    const fillCount = Number(metadata.fill_count || 0);
    return {
      ...base,
      type: Number.isFinite(fillCount) && fillCount > 0 ? "trade" : "decision",
      action,
      ticker: metadata.ticker || null,
      quantity: metadata.quantity || null,
      fill_count: Number.isFinite(fillCount) ? fillCount : 0,
      hold_cause: null,
    };
  }

  if (row.event_type === "execution" && row.stage === "order_rejected") {
    return {
      ...base,
      type: "decision",
      action: "HOLD",
      ticker: null,
      quantity: null,
      fill_count: 0,
      hold_cause: metadata.hold_cause || "risk_limit",
    };
  }

  return null;
}

function useRecentChartEvents() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const payload = await getAgentActivity({ limit: 150 });
        if (cancelled) return;
        setEvents((payload?.activity || []).map(activityToChartEvent).filter(Boolean));
      } catch {
        // Keep the last successful activity window when the database is transiently unavailable.
      }
    }

    load();
    const timer = setInterval(load, CHART_EVENT_POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return events;
}

function sameChartEvent(left, right) {
  if (left.decision_id != null && right.decision_id != null) {
    return String(left.decision_id) === String(right.decision_id);
  }
  if (left.bot_id !== right.bot_id || left.action !== right.action || left.ticker !== right.ticker) return false;
  const leftTime = new Date(left.timestamp).getTime();
  const rightTime = new Date(right.timestamp).getTime();
  return Number.isFinite(leftTime) && Number.isFinite(rightTime) && Math.abs(leftTime - rightTime) <= 5_000;
}

function mergeChartEvents(socketEvents, persistedEvents) {
  const merged = [];
  [...socketEvents, ...persistedEvents]
    .filter((event) => event?.bot_id && event?.timestamp)
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .forEach((event) => {
      if (merged.some((existing) => sameChartEvent(existing, event))) return;
      merged.push(event);
    });
  return merged;
}

function eventMarkerColor(event) {
  if (String(event.action || "").toUpperCase() === "BUY") return "#059669";
  if (String(event.action || "").toUpperCase() === "SELL") return "#E11D48";
  return "#64748B";
}

function nearestChartPoint(chartData, timestamp) {
  const target = new Date(timestamp).getTime();
  if (!Number.isFinite(target)) return null;

  let nearest = null;
  let distance = Infinity;
  chartData.forEach((row) => {
    const pointTime = new Date(row.rawTs).getTime();
    const pointDistance = Math.abs(pointTime - target);
    if (Number.isFinite(pointDistance) && pointDistance < distance) {
      nearest = row;
      distance = pointDistance;
    }
  });
  return nearest;
}

function buildEventMarkers(events, chartData, series, bots, viewMode, selectedBotId, timeRange) {
  if (!events.length || !chartData.length || !series.length) return [];

  const cutoff = cutoffForRange(timeRange);
  const botsById = new Map(bots.map((bot) => [bot.bot_id, bot]));
  const seriesIds = new Set(series.map((item) => item.id));
  const seen = new Set();
  const markers = [];

  [...events]
    .filter((event) => event.type === "trade" || event.type === "decision")
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .forEach((event) => {
      const eventTime = new Date(event.timestamp).getTime();
      const bot = botsById.get(event.bot_id);
      if (!bot || !Number.isFinite(eventTime) || eventTime < cutoff) return;
      if (viewMode === "bot" && event.bot_id !== selectedBotId) return;

      const identity = liveEventIdentity(event);
      if (seen.has(identity)) return;
      seen.add(identity);

      const dataKey = viewMode === "teams"
        ? bot.llm_provider === "claude" ? "team-claude" : "team-openai"
        : event.bot_id;
      if (!seriesIds.has(dataKey)) return;

      const point = nearestChartPoint(chartData, event.timestamp);
      if (!point || point[dataKey] == null) return;
      markers.push({
        ...event,
        id: identity,
        dataKey,
        time: point.time,
        value: Number(point[dataKey]),
        color: eventMarkerColor(event),
        botLabel: `${shortName(bot.name)} ${providerLabel(bot)}`,
      });
    });

  return markers.slice(0, 10);
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
    <div className="max-w-[280px] rounded-lg border border-border bg-white p-3 text-xs shadow-lg">
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
        "min-w-[68px] flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors sm:flex-none sm:min-w-[76px]",
        active ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
      ].join(" ")}
    >
      {mode.label}
    </button>
  );
}

function TinyStat({ label, value, sub, color = "#0F172A" }) {
  return (
    <div className="min-w-0 rounded-md border border-border bg-white px-4 py-3">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className="mt-1 truncate text-lg font-semibold tabular-nums" style={{ color }}>
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
    <div className={`rounded-lg border border-border ${bgClass} px-4 py-3`}>
      <div className={`flex items-center gap-2 ${isRight ? "justify-end" : ""}`}>
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <div className="text-xs font-medium text-slate-600">{team} average</div>
      </div>
      <div className={`mt-2 text-xl font-semibold tabular-nums ${signClass}`}>
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
          <div key={item.id} className="flex min-w-0 items-center justify-between gap-2 rounded-md border border-border bg-white px-3 py-2">
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

function BenchmarkReference({ ticker, row }) {
  const benchmarkReturn = Number(row?.avg_benchmark_return) * 100;
  const excessReturn = Number(row?.avg_excess_return) * 100;
  if (!row || !Number.isFinite(benchmarkReturn)) return null;
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-border bg-white px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full border-2 border-slate-500" />
        <span className="font-mono text-xs font-semibold text-slate-700">{ticker}</span>
      </div>
      <div className="text-right">
        <div className="font-mono text-xs font-semibold text-slate-700">{pct(benchmarkReturn)} benchmark</div>
        <div className={`font-mono text-[11px] ${excessReturn >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{pct(excessReturn)} agent excess</div>
      </div>
    </div>
  );
}

function LiveEventStrip({ markers }) {
  return (
    <div className="border-t border-border px-2 pb-1 pt-3 sm:px-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          Live event markers
        </span>
        <span className="font-mono text-[11px] text-slate-400">
          {markers.length ? `${markers.length} in range` : "none in range"}
        </span>
      </div>
      {markers.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {markers.slice(0, 5).map((event) => {
            const action = String(event.action || "").toUpperCase();
            const isHold = action === "HOLD";
            const outcome = isHold
              ? event.hold_cause ? holdCauseLabel(event.hold_cause) : "Held"
              : event.type === "trade" || Number(event.fill_count || 0) > 0 ? "filled" : "submitted";
            return (
              <span
                key={event.id}
                className="inline-flex min-w-0 items-center gap-1.5 border border-border bg-slate-50 px-2 py-1 font-mono text-[11px] text-slate-600"
                title={event.reasoning || undefined}
              >
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: event.color }} />
                <strong className="text-ink">{action || "EVENT"}</strong>
                <span className="max-w-[130px] truncate">{event.botLabel}</span>
                {event.ticker ? <span className="font-semibold text-ink">{event.ticker}</span> : null}
                <span className="text-slate-400">{outcome}</span>
              </span>
            );
          })}
        </div>
      ) : (
        <p className="mt-2 font-mono text-xs text-slate-400">No live decisions landed in this time window.</p>
      )}
    </div>
  );
}

export default function ComparisonChart({ evaluation }) {
  const [viewMode, setViewMode] = useState("teams");
  const [timeRange, setTimeRange] = useState("1D");
  const [selectedBotId, setSelectedBotId] = useState("");

  const { claudeBots, gptBots, loading: botsLoading } = useBots();
  const allBots = useMemo(() => [...claudeBots, ...gptBots], [claudeBots, gptBots]);
  const allBotIds = useMemo(() => allBots.map((bot) => bot.bot_id), [allBots]);
  const startingCashById = useMemo(
    () => new Map(allBots.map((bot) => [bot.bot_id, startingCashFor(bot, DEFAULT_STARTING_CASH)])),
    [allBots]
  );
  const { reasoningMap, loading: reasoningLoading } = useAllBotReasoning(allBotIds, 500, startingCashById);
  const liveSamples = useLiveValueSamples(allBots);
  const { events: liveEvents } = useWebSocket();
  const persistedEvents = useRecentChartEvents();
  const chartEvents = useMemo(
    () => mergeChartEvents(liveEvents, persistedEvents),
    [liveEvents, persistedEvents]
  );

  useEffect(() => {
    if (!selectedBotId && allBots.length) setSelectedBotId(allBots[0].bot_id);
  }, [allBots, selectedBotId]);

  const visibleBots = useMemo(() => {
    if (viewMode === "bot") return allBots.filter((bot) => bot.bot_id === selectedBotId);
    return allBots;
  }, [allBots, selectedBotId, viewMode]);

  const nowIso = useMemo(() => new Date().toISOString(), [reasoningMap, allBots]);
  const botSeries = useMemo(
    () => visibleBots.map((bot, index) => buildBotSeries(bot, reasoningMap, liveSamples, botColor(bot, index), nowIso)),
    [nowIso, reasoningMap, liveSamples, visibleBots]
  );
  const allSeries = useMemo(
    () => allBots.map((bot, index) => buildBotSeries(bot, reasoningMap, liveSamples, botColor(bot, index), nowIso)),
    [allBots, liveSamples, nowIso, reasoningMap]
  );
  const series = useMemo(() => {
    if (viewMode !== "teams") return botSeries;
    return [
      buildTeamSeries({
        id: "team-claude",
        label: "Claude average",
        provider: "claude",
        color: "#3157D5",
        items: allSeries.filter((item) => item.provider === "claude"),
      }),
      buildTeamSeries({
        id: "team-openai",
        label: "OpenAI average",
        provider: "openai",
        color: "#B95818",
        items: allSeries.filter((item) => item.provider === "openai"),
      }),
    ];
  }, [allSeries, botSeries, viewMode]);
  const chartData = useMemo(() => buildChartData(series, timeRange), [series, timeRange]);
  const eventMarkers = useMemo(
    () => buildEventMarkers(chartEvents, chartData, series, allBots, viewMode, selectedBotId, timeRange),
    [allBots, chartData, chartEvents, selectedBotId, series, timeRange, viewMode]
  );

  const claudeAvg = averageReturn(claudeBots);
  const openaiAvg = averageReturn(gptBots);
  const claudeAvgPnl = averagePnl(claudeBots);
  const openaiAvgPnl = averagePnl(gptBots);
  const spread = claudeAvgPnl - openaiAvgPnl;
  const leader = leaderFor(allBots);
  const leadingTeam = Math.abs(spread) < 1 ? "Even" : spread > 0 ? "Claude" : "OpenAI";
  const benchmarkRows = evaluation?.benchmark_comparison?.by_benchmark || {};
  const benchmarkLines = [
    { ticker: "SPY", color: "#64748B", value: Number(benchmarkRows.SPY?.avg_benchmark_return) * 100 },
    { ticker: "QQQ", color: "#B95818", value: Number(benchmarkRows.QQQ?.avg_benchmark_return) * 100 },
  ].filter((item) => Number.isFinite(item.value));

  if (botsLoading) {
    return (
      <div className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-56 rounded bg-slate-200" />
          <div className="h-[340px] rounded-lg bg-slate-100" />
        </div>
      </div>
    );
  }

  return (
    <section className="space-y-5 rounded-lg border border-border bg-white p-4 shadow-sm sm:p-5 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Agent portfolios · identical market inputs
          </div>
          <div className="mt-3 flex items-start gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              Agent performance
            </h1>
            <InfoTooltip label="Is this read-only?">
              Yes. Public visitors can inspect the arena, but only the backend scheduler can advance agents and submit
              simulated orders through risk checks.
            </InfoTooltip>
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            This is the main experiment: the same market inputs go to each trader, and the chart shows how their
            simulated portfolios behave. SPY and QQQ references make the result interpretable instead of treating
            raw NVIDIA movement as the score.
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
          color="#3157D5"
          bgClass="bg-soft-blue"
        />
        <div className="flex min-h-[96px] items-center justify-center rounded-lg border border-border bg-slate-50 px-6 text-center">
          <div>
            <div className="text-xs font-medium text-slate-500">Current leader</div>
            <div className="mt-1 text-xl font-semibold text-ink">{leadingTeam}</div>
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
          color="#B95818"
          bgClass="bg-soft-orange"
          align="right"
        />
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex w-full flex-wrap gap-1 rounded-lg border border-border bg-slate-50 p-1 sm:w-auto">
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
            className="min-h-[40px] w-full rounded-md border border-border bg-white px-4 py-2 text-sm font-medium text-slate-700 outline-none transition-colors focus:border-claude sm:w-auto"
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
        <TinyStat label="View" value={VIEW_MODES.find((mode) => mode.value === viewMode)?.label || "Teams"} sub={timeRange} />
        <TinyStat label="Visible Lines" value={String(series.length)} sub={viewMode === "teams" ? "team averages" : "bot traces"} color="#334155" />
        <TinyStat
          label="Top Bot"
          value={leader ? shortName(leader.name) : "n/a"}
          sub={
            leader
              ? `${providerLabel(leader)} ${pct(returnPct(leader.total_value, startingCashFor(leader)))} (${formatDollar(leader.total_value)})`
              : null
          }
          color={leader?.llm_provider === "claude" ? "#3157D5" : "#B95818"}
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-white p-2 sm:p-3">
        {chartData.length === 0 ? (
          <div className="flex h-[340px] items-center justify-center">
            <p className="font-mono text-sm text-slate-500">
              {reasoningLoading ? "Loading chart data..." : "Waiting for first decisions..."}
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
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
                domain={[
                  (dataMin) => Math.min(dataMin, 0, ...benchmarkLines.map((line) => line.value)),
                  (dataMax) => Math.max(dataMax, 0, ...benchmarkLines.map((line) => line.value)),
                ]}
              />
              <ReferenceLine y={0} stroke="#94A3B8" strokeDasharray="4 4" />
              {benchmarkLines.map((line) => (
                <ReferenceLine
                  key={line.ticker}
                  y={line.value}
                  stroke={line.color}
                  strokeDasharray="6 4"
                  label={{ value: `${line.ticker} ${pct(line.value)}`, fill: line.color, fontSize: 10, position: "right" }}
                />
              ))}
              <Tooltip content={<CustomTooltip />} />
              {series.map((item) => (
                <Line
                  key={item.id}
                  dataKey={item.id}
                  name={item.label}
                  stroke={item.color}
                  strokeWidth={viewMode === "bot" || viewMode === "teams" ? 3 : 2.25}
                  strokeOpacity={viewMode === "all" ? 0.72 : 0.95}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
              {eventMarkers.map((event) => (
                <ReferenceDot
                  key={event.id}
                  x={event.time}
                  y={event.value}
                  r={5}
                  fill={event.color}
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  ifOverflow="visible"
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
        <LiveEventStrip markers={eventMarkers} />
      </div>

      <div className="rounded-md border border-border bg-slate-50 px-3 py-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Benchmark references</div>
            <p className="mt-1 text-xs text-slate-600">Dashed lines use average SPY and QQQ returns from evaluated trade windows.</p>
          </div>
          <span className="font-mono text-[11px] text-slate-400">{evaluation?.benchmark_comparison?.comparison_count || 0} comparisons</span>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <BenchmarkReference ticker="SPY" row={benchmarkRows.SPY} />
          <BenchmarkReference ticker="QQQ" row={benchmarkRows.QQQ} />
        </div>
      </div>

      <Legend series={series} />
      <div className="sr-only">{teamValue(claudeAvgPnl, claudeAvg)} vs {teamValue(openaiAvgPnl, openaiAvg)}</div>
    </section>
  );
}
