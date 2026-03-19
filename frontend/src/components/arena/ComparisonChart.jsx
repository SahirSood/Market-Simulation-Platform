import { useState, useMemo } from "react";
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

import { useBots }             from "../../hooks/useBots";
import { useAllBotReasoning }  from "../../hooks/useAllBotReasoning";
import {
  getTeamSeries,
  buildChartData,
  formatDollar,
  formatPnl,
  formatPnlPct,
} from "../../lib/chartUtils";

import BotDropdown      from "./BotDropdown";
import WinnerBadge      from "./WinnerBadge";
import TimeRangeToggle  from "./TimeRangeToggle";

const STARTING_CASH = 100_000;

// ── Custom tooltip ────────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const claude = payload.find((p) => p.dataKey === "claude")?.value;
  const gpt    = payload.find((p) => p.dataKey === "gpt")?.value;
  return (
    <div className="bg-panel border border-border rounded-lg p-3 text-xs font-mono shadow-lg">
      <p className="text-[#64748B] mb-2">{label}</p>
      {claude != null && (
        <p className="text-claude">
          🔵 Claude&nbsp;&nbsp;{formatDollar(claude)}
        </p>
      )}
      {gpt != null && (
        <p className="text-gpt mt-1">
          🟠 GPT&nbsp;&nbsp;&nbsp;&nbsp;{formatDollar(gpt)}
        </p>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ComparisonChart() {
  const [claudeSel, setClaudeSel] = useState("average");
  const [gptSel,    setGptSel]    = useState("average");
  const [timeRange, setTimeRange] = useState("1D");

  const { claudeBots, gptBots, loading: botsLoading } = useBots();

  // Collect all bot IDs to fetch reasoning for
  const allBotIds = useMemo(
    () => [...claudeBots, ...gptBots].map((b) => b.bot_id),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [claudeBots.map((b) => b.bot_id).join(","), gptBots.map((b) => b.bot_id).join(",")]
  );

  const { reasoningMap, loading: reasoningLoading } = useAllBotReasoning(allBotIds);

  // ── Build chart data ────────────────────────────────────────────────────────
  const { chartData, claudeLastVal, gptLastVal } = useMemo(() => {
    if (!claudeBots.length || !gptBots.length) {
      return { chartData: [], claudeLastVal: STARTING_CASH, gptLastVal: STARTING_CASH };
    }

    const claudeSeries = getTeamSeries(claudeBots, claudeSel, reasoningMap);
    const gptSeries    = getTeamSeries(gptBots,    gptSel,    reasoningMap);
    const data         = buildChartData(claudeSeries, gptSeries, timeRange);

    const last = data[data.length - 1];
    return {
      chartData:     data,
      claudeLastVal: last?.claude ?? STARTING_CASH,
      gptLastVal:    last?.gpt    ?? STARTING_CASH,
    };
  }, [claudeBots, gptBots, claudeSel, gptSel, timeRange, reasoningMap]);

  const claudeIsWinning = claudeLastVal >= gptLastVal;
  const gptIsWinning    = !claudeIsWinning;

  // ── Current values for the selected display ─────────────────────────────────
  const claudeCurrentBot = useMemo(() => {
    if (claudeSel === "average") return null;
    return claudeBots.find((b) => b.bot_id.startsWith(claudeSel));
  }, [claudeBots, claudeSel]);

  const gptCurrentBot = useMemo(() => {
    if (gptSel === "average") return null;
    return gptBots.find((b) => b.bot_id.startsWith(gptSel));
  }, [gptBots, gptSel]);

  // ── Loading skeleton ────────────────────────────────────────────────────────
  if (botsLoading) {
    return (
      <div className="bg-panel border border-border rounded-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-5 bg-[#1E1E2E] rounded w-48" />
          <div className="h-[320px] bg-[#1E1E2E] rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-panel border border-border rounded-xl p-6 space-y-5">

      {/* Header row */}
      <div className="flex items-center justify-between">
        <h2 className="text-[#F1F5F9] font-semibold text-base tracking-tight">
          CLAUDE vs GPT-4o
        </h2>
        <TimeRangeToggle value={timeRange} onChange={setTimeRange} />
      </div>

      {/* Dropdown + WinnerBadge row */}
      <div className="flex items-end gap-4">
        <BotDropdown team="claude" value={claudeSel} onChange={setClaudeSel} />

        <div className="flex-1 flex justify-center pb-1">
          <WinnerBadge claudeVal={claudeLastVal} gptVal={gptLastVal} />
        </div>

        <BotDropdown team="gpt" value={gptSel} onChange={setGptSel} />
      </div>

      {/* Chart */}
      {chartData.length === 0 ? (
        <div className="h-[320px] flex items-center justify-center">
          <p className="text-[#64748B] text-sm font-mono">
            {reasoningLoading ? "Loading chart data…" : "Waiting for first decisions…"}
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
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
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              tickLine={false}
              axisLine={false}
              domain={["auto", "auto"]}
              width={52}
            />
            <ReferenceLine
              y={STARTING_CASH}
              stroke="#334155"
              strokeDasharray="4 4"
              label={{ value: "$100k", fill: "#334155", fontSize: 10, position: "insideTopLeft" }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              dataKey="claude"
              stroke="#3B82F6"
              strokeWidth={claudeIsWinning ? 3 : 1.5}
              strokeOpacity={claudeIsWinning ? 1 : 0.35}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="gpt"
              stroke="#F97316"
              strokeWidth={gptIsWinning ? 3 : 1.5}
              strokeOpacity={gptIsWinning ? 1 : 0.35}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {/* Value display below chart */}
      <div className="flex justify-between pt-1 border-t border-border">
        <ValueDisplay
          label={claudeSel === "average" ? "Claude Average" : `Claude ${capitalize(claudeSel)}`}
          value={claudeLastVal}
          color="#3B82F6"
        />
        <ValueDisplay
          label={gptSel === "average" ? "GPT Average" : `GPT ${capitalize(gptSel)}`}
          value={gptLastVal}
          color="#F97316"
          align="right"
        />
      </div>

    </div>
  );
}

function ValueDisplay({ label, value, color, align = "left" }) {
  const pnl    = value - 100_000;
  const pnlPct = ((pnl / 100_000) * 100).toFixed(2);
  const pnlSign = pnl >= 0 ? "+" : "";
  const pnlColor = pnl >= 0 ? "#22C55E" : "#EF4444";

  return (
    <div className={`flex flex-col gap-0.5 ${align === "right" ? "items-end" : "items-start"}`}>
      <span className="text-[10px] font-mono text-[#64748B] tracking-wide">{label}</span>
      <span className="font-mono font-bold text-lg" style={{ color }}>
        {formatDollar(value)}
      </span>
      <span className="font-mono text-xs" style={{ color: pnlColor }}>
        {pnlSign}{formatDollar(pnl)}&nbsp;({pnlSign}{pnlPct}%)
      </span>
    </div>
  );
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
