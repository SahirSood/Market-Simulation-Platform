import { useEffect, useMemo, useState } from "react";

import { getBotDetail } from "../../api/endpoints";
import { useBots } from "../../hooks/useBots";
import { useOrderBook } from "../../hooks/useOrderBook";
import { formatDollar, providerLabel, shortName } from "../../lib/botUtils";

function PositionsPanel() {
  const { claudeBots, gptBots } = useBots();
  const bots = useMemo(() => [...claudeBots, ...gptBots], [claudeBots, gptBots]);
  const [details, setDetails] = useState([]);

  useEffect(() => {
    if (!bots.length) return undefined;
    let cancelled = false;
    async function load() {
      const rows = await Promise.all(bots.map((bot) => getBotDetail(bot.bot_id)));
      if (!cancelled) setDetails(rows.filter(Boolean));
    }
    load();
    const timer = setInterval(load, 30_000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [bots]);

  const positions = details.flatMap((bot) => (bot.positions || []).map((position) => ({ ...position, bot })));
  const totalValue = bots.reduce((sum, bot) => sum + Number(bot.total_value || 0), 0);
  const unrealized = bots.reduce((sum, bot) => sum + Number(bot.unrealized_pnl || 0), 0);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-4 sm:px-5">
        <div>
          <h2 className="text-lg font-semibold text-ink">Open positions</h2>
          <p className="mt-1 text-sm text-slate-600">Live portfolios after fills from the matching engine.</p>
        </div>
        <div className="text-right">
          <div className="font-mono text-sm font-semibold text-ink">{formatDollar(totalValue)}</div>
          <div className={`font-mono text-xs ${unrealized >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{unrealized >= 0 ? "+" : ""}{formatDollar(unrealized)} unrealized</div>
        </div>
      </div>
      <div className="max-h-[330px] overflow-auto">
        {positions.length ? (
          <table className="w-full min-w-[620px] text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-[10px] uppercase text-slate-500">
              <tr><th className="px-4 py-2">Agent</th><th className="px-3 py-2">Ticker</th><th className="px-3 py-2 text-right">Shares</th><th className="px-3 py-2 text-right">Avg cost</th><th className="px-3 py-2 text-right">Mark</th><th className="px-4 py-2 text-right">Unrealized</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {positions.slice(0, 16).map((row) => (
                <tr key={`${row.bot.bot_id}-${row.ticker}`}>
                  <td className="px-4 py-2.5"><span className="font-semibold text-ink">{shortName(row.bot.name)}</span><span className="ml-1 text-slate-400">{providerLabel(row.bot)}</span></td>
                  <td className="px-3 py-2.5 font-mono font-semibold">{row.ticker}</td>
                  <td className="px-3 py-2.5 text-right font-mono">{Number(row.quantity).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-right font-mono">{formatDollar(row.avg_cost)}</td>
                  <td className="px-3 py-2.5 text-right font-mono">{formatDollar(row.current_price)}</td>
                  <td className={`px-4 py-2.5 text-right font-mono ${Number(row.unrealized_pnl) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{Number(row.unrealized_pnl) >= 0 ? "+" : ""}{formatDollar(row.unrealized_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <div className="grid min-h-[220px] place-items-center px-5 text-center text-sm text-slate-500">No open positions yet. Decisions and rejected orders can still appear in the tape.</div>}
      </div>
    </section>
  );
}

function Level({ level, side, max }) {
  const width = max ? Math.max(8, (Number(level.quantity || 0) / max) * 100) : 0;
  return (
    <div className="relative grid grid-cols-2 overflow-hidden border-b border-border px-3 py-2 last:border-b-0">
      <div className={`absolute inset-y-0 ${side === "bid" ? "right-0 bg-emerald-50" : "left-0 bg-rose-50"}`} style={{ width: `${width}%` }} />
      <span className={`relative font-mono text-xs font-semibold ${side === "bid" ? "text-emerald-700" : "text-rose-700"}`}>${Number(level.price).toFixed(2)}</span>
      <span className="relative text-right font-mono text-xs text-slate-600">{Number(level.quantity || 0).toLocaleString()}</span>
    </div>
  );
}

function OrderBookPreview({ ticker }) {
  const { orderBook, loading, error } = useOrderBook();
  const snapshot = orderBook?.find((item) => item.ticker === ticker) || orderBook?.[0];
  const bids = (snapshot?.bids || []).slice(0, 5);
  const asks = (snapshot?.asks || []).slice(0, 5);
  const max = Math.max(0, ...bids.map((row) => Number(row.quantity || 0)), ...asks.map((row) => Number(row.quantity || 0)));
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-4 sm:px-5">
        <div><h2 className="text-lg font-semibold text-ink">C++ order book</h2><p className="mt-1 text-sm text-slate-600">Best visible resting liquidity.</p></div>
        <div className="text-right"><div className="font-mono text-sm font-semibold text-ink">{snapshot?.ticker || ticker}</div><div className="text-xs text-slate-500">{snapshot?.trade_count || 0} matched trades</div></div>
      </div>
      {loading && !snapshot ? <div className="grid min-h-[220px] place-items-center text-sm text-slate-500">Loading book...</div> : error && !snapshot ? <div className="m-4 bg-rose-50 px-3 py-2 text-sm text-rose-700">Order book unavailable.</div> : (
        <div className="grid grid-cols-2 divide-x divide-border">
          <div><div className="grid grid-cols-2 bg-slate-50 px-3 py-2 text-[10px] uppercase text-slate-500"><span>Bid</span><span className="text-right">Qty</span></div>{bids.length ? bids.map((row) => <Level key={`bid-${row.price}`} level={row} side="bid" max={max} />) : <div className="p-6 text-center text-xs text-slate-500">No bids</div>}</div>
          <div><div className="grid grid-cols-2 bg-slate-50 px-3 py-2 text-[10px] uppercase text-slate-500"><span>Ask</span><span className="text-right">Qty</span></div>{asks.length ? asks.map((row) => <Level key={`ask-${row.price}`} level={row} side="ask" max={max} />) : <div className="p-6 text-center text-xs text-slate-500">No asks</div>}</div>
        </div>
      )}
    </section>
  );
}

export default function TradingSnapshot({ ticker }) {
  return <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]"><PositionsPanel /><OrderBookPreview ticker={ticker} /></div>;
}
