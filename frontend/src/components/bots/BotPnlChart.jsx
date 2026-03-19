import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, Tooltip, ReferenceLine,
} from "recharts";

const STARTING_CASH = 100_000;

/**
 * reasoning: ReasoningEntry[] (from useBotDetail)
 * color: team hex color string
 */
export default function BotPnlChart({ reasoning, color }) {
  const data = reasoning
    .filter((r) => r?.portfolio_snapshot?.total_value != null)
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .map((r) => ({
      time:  new Date(r.timestamp).toLocaleTimeString("en-US", {
        hour: "2-digit", minute: "2-digit", hour12: false,
      }),
      value: Math.round(r.portfolio_snapshot.total_value),
    }));

  if (data.length === 0) {
    return (
      <div className="h-[180px] flex items-center justify-center">
        <p className="text-[#64748B] text-xs font-mono">No history yet</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <XAxis
          dataKey="time"
          hide={data.length < 3}
          stroke="#334155"
          tick={{ fill: "#64748B", fontFamily: "JetBrains Mono", fontSize: 10 }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          stroke="#334155"
          tick={{ fill: "#64748B", fontFamily: "JetBrains Mono", fontSize: 10 }}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          tickLine={false}
          axisLine={false}
          domain={["auto", "auto"]}
          width={44}
        />
        <ReferenceLine
          y={STARTING_CASH}
          stroke="#334155"
          strokeDasharray="4 4"
        />
        <Tooltip
          contentStyle={{
            background: "#111118", border: "1px solid #1E1E2E",
            borderRadius: "8px", fontFamily: "JetBrains Mono", fontSize: 11,
          }}
          formatter={(v) => [`$${v.toLocaleString()}`, "Value"]}
          labelStyle={{ color: "#64748B" }}
        />
        <Line
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
