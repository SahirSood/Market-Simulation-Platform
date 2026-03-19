import { useMemo } from "react";
import { useWebSocket }    from "../../hooks/useWebSocket";
import { useOrderBook }    from "../../hooks/useOrderBook";
import { useLeaderboard }  from "../../hooks/useLeaderboard";

export default function StatBar() {
  const { events }         = useWebSocket();
  const { orderBook }      = useOrderBook();
  const { leaderboard }    = useLeaderboard();

  // Count trade events from WebSocket (type === "trade")
  const tradeCount = useMemo(
    () => events.filter((e) => e.type === "trade").length,
    [events]
  );

  // Active tickers from orderbook
  const tickers = useMemo(() => {
    if (!orderBook || !Array.isArray(orderBook)) return [];
    return orderBook.map((b) => b.ticker).filter(Boolean);
  }, [orderBook]);

  // Winner: compare sum of alltime_pnl by team
  const winner = useMemo(() => {
    if (!leaderboard?.length) return null;
    let claudePnl = 0;
    let gptPnl    = 0;
    leaderboard.forEach((e) => {
      // bot_id ends in "-claude" or "-openai"
      if (e.bot_id?.includes("claude")) claudePnl += e.alltime_pnl;
      else                               gptPnl    += e.alltime_pnl;
    });
    const avgClaude = claudePnl / 5;
    const avgGpt    = gptPnl    / 5;
    if (Math.abs(avgClaude - avgGpt) < 1) return null;
    const team = avgClaude > avgGpt ? "Claude" : "GPT";
    const pct  = (Math.abs(avgClaude - avgGpt) / 100_000) * 100;
    return { team, pct: pct.toFixed(2), color: avgClaude > avgGpt ? "#3B82F6" : "#F97316" };
  }, [leaderboard]);

  return (
    <div className="bg-panel border-y border-border py-3 px-6 flex items-center gap-4 text-xs font-mono text-[#64748B] overflow-x-auto">

      {/* Trade count */}
      <span className="shrink-0">
        <span className="text-[#F1F5F9]">{tradeCount}</span> trades live
      </span>

      <Divider />

      {/* Active tickers */}
      {tickers.length > 0 ? (
        <div className="flex items-center gap-1.5 shrink-0">
          {tickers.map((t) => (
            <span
              key={t}
              className="bg-border rounded px-2 py-0.5 text-[#F1F5F9] text-[10px] font-mono font-semibold"
            >
              {t}
            </span>
          ))}
        </div>
      ) : (
        <span className="shrink-0">No active tickers</span>
      )}

      {winner && (
        <>
          <Divider />
          <span className="shrink-0" style={{ color: winner.color }}>
            🏆 {winner.team} +{winner.pct}%
          </span>
        </>
      )}
    </div>
  );
}

function Divider() {
  return <span className="text-[#334155] select-none">·</span>;
}
