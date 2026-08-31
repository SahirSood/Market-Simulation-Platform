import { useMemo } from "react";
import { useLeaderboard } from "../../hooks/useLeaderboard";
import { useOrderBook } from "../../hooks/useOrderBook";

export default function StatBar() {
  const { orderBook } = useOrderBook();
  const { leaderboard } = useLeaderboard();

  const tradeCount = useMemo(
    () => (leaderboard || []).reduce((sum, row) => sum + Number(row.trade_count_today || 0), 0),
    [leaderboard]
  );

  const tickers = useMemo(() => {
    if (!Array.isArray(orderBook)) return [];
    return orderBook
      .filter((book) => (book.bids?.length || 0) + (book.asks?.length || 0) > 0)
      .map((book) => book.ticker)
      .filter(Boolean);
  }, [orderBook]);

  const winner = useMemo(() => {
    if (!leaderboard?.length) return null;
    let claudePnl = 0;
    let openaiPnl = 0;
    leaderboard.forEach((row) => {
      if (row.bot_id?.includes("claude")) claudePnl += Number(row.alltime_pnl || 0);
      else openaiPnl += Number(row.alltime_pnl || 0);
    });
    const claudeRows = leaderboard.filter((row) => row.bot_id?.includes("claude"));
    const openaiRows = leaderboard.filter((row) => row.bot_id?.includes("openai"));
    const avgClaude = claudeRows.length ? claudePnl / claudeRows.length : 0;
    const avgOpenAI = openaiRows.length ? openaiPnl / openaiRows.length : 0;
    if (Math.abs(avgClaude - avgOpenAI) < 1) return null;
    const claudeLeading = avgClaude > avgOpenAI;
    const pct = (Math.abs(avgClaude - avgOpenAI) / 100_000) * 100;
    return {
      team: claudeLeading ? "Claude" : "OpenAI",
      pct: pct.toFixed(2),
      color: claudeLeading ? "#3157D5" : "#B95818",
    };
  }, [leaderboard]);

  return (
    <div className="grid overflow-hidden rounded-lg border border-border bg-white shadow-sm sm:grid-cols-3">
      <Metric label="Decisions today" value={tradeCount} detail="submitted trades and fills" />
      <Metric
        label="Markets"
        value={tickers.length || "—"}
        detail={tickers.length ? `${tickers.slice(0, 5).join(", ")}${tickers.length > 5 ? ` +${tickers.length - 5}` : ""}` : "waiting for order books"}
      />
      <Metric
        label="Provider lead"
        value={winner ? `${winner.team} +${winner.pct}%` : "Even"}
        detail="average portfolio return"
        color={winner?.color}
      />
    </div>
  );
}

function Metric({ label, value, detail, color }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-ink" style={color ? { color } : undefined}>
        {value}
      </div>
      <div className="mt-0.5 truncate text-xs text-slate-500">{detail}</div>
    </div>
  );
}
