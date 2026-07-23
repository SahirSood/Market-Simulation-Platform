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
    return orderBook.map((book) => book.ticker).filter(Boolean);
  }, [orderBook]);

  const winner = useMemo(() => {
    if (!leaderboard?.length) return null;
    let claudePnl = 0;
    let openaiPnl = 0;
    leaderboard.forEach((row) => {
      if (row.bot_id?.includes("claude")) claudePnl += Number(row.alltime_pnl || 0);
      else openaiPnl += Number(row.alltime_pnl || 0);
    });
    const avgClaude = claudePnl / 5;
    const avgOpenAI = openaiPnl / 5;
    if (Math.abs(avgClaude - avgOpenAI) < 1) return null;
    const claudeLeading = avgClaude > avgOpenAI;
    const pct = (Math.abs(avgClaude - avgOpenAI) / 100_000) * 100;
    return {
      team: claudeLeading ? "Claude" : "OpenAI",
      pct: pct.toFixed(2),
      color: claudeLeading ? "#2563EB" : "#F97316",
    };
  }, [leaderboard]);

  return (
    <div className="flex items-center gap-3 overflow-x-auto rounded-xl border border-border bg-white px-4 py-3 font-mono text-xs text-slate-500 shadow-sm">
      <span className="shrink-0">
        <span className="font-bold text-ink">{tradeCount}</span> trade decisions today
      </span>

      <Divider />

      {tickers.length > 0 ? (
        <div className="flex shrink-0 items-center gap-1.5">
          <span className="font-bold text-ink">{tickers.length}</span>
          <span>symbols</span>
          {tickers.slice(0, 5).map((ticker) => (
            <span
              key={ticker}
              className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-[10px] font-semibold text-slate-700"
            >
              {ticker}
            </span>
          ))}
          {tickers.length > 5 ? <span className="text-slate-400">+{tickers.length - 5}</span> : null}
        </div>
      ) : (
        <span className="shrink-0">No active tickers</span>
      )}

      {winner ? (
        <>
          <Divider />
          <span className="shrink-0" style={{ color: winner.color }}>
            {winner.team} +{winner.pct}%
          </span>
        </>
      ) : null}
    </div>
  );
}

function Divider() {
  return <span className="select-none text-slate-300">/</span>;
}
