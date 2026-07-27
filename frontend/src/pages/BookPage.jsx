import { useEffect, useState } from "react";
import OrderBookPanel from "../components/book/OrderBookPanel";
import Skeleton from "../components/ui/Skeleton";
import { useOrderBook } from "../hooks/useOrderBook";

function OrderBookError({ error, refetch }) {
  return (
    <div className="flex items-center gap-3 bg-rose-50 border border-rose-200 rounded-xl px-5 py-3 text-sm">
      <span className="text-rose-600">{error}</span>
      <button onClick={refetch} className="text-rose-600 text-xs font-mono underline ml-auto">
        Retry
      </button>
    </div>
  );
}

export default function BookPage() {
  const { orderBook, loading, error, lastUpdated, refetch } = useOrderBook();
  const [activeTicker, setActiveTicker] = useState("");

  useEffect(() => {
    if (!orderBook?.length) return;
    if (!activeTicker || !orderBook.some((snapshot) => snapshot.ticker === activeTicker)) {
      setActiveTicker(orderBook[0].ticker);
    }
  }, [orderBook, activeTicker]);

  const activeSnapshot = orderBook?.find((snapshot) => snapshot.ticker === activeTicker);
  const hasBook = Boolean(orderBook?.length);
  const updatedLabel = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : null;

  return (
    <div className="mx-auto max-w-[1280px] space-y-5 px-4 py-6 md:px-8 md:py-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Order book</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            See the buyers and sellers currently waiting in each simulated market. Values update in place without
            clearing the screen.
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:min-w-[220px]">
          <label htmlFor="market-ticker" className="text-xs font-medium text-slate-500">
            Market ticker
          </label>
          <select
            id="market-ticker"
            value={activeTicker}
            onChange={(event) => setActiveTicker(event.target.value)}
            disabled={!hasBook}
            className="min-h-[42px] rounded-md border border-border bg-white px-3 py-2 font-mono text-sm font-semibold text-ink outline-none transition-colors focus:border-claude disabled:text-slate-400"
          >
            {!hasBook ? <option value="">Waiting for markets</option> : null}
            {(orderBook ?? []).map((snapshot) => (
              <option key={snapshot.ticker} value={snapshot.ticker}>
                {snapshot.ticker}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-white px-4 py-3 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${error ? "bg-amber-500" : "bg-emerald-500"}`} />
          <span>{error && hasBook ? "Showing the last good snapshot" : "Live market data"}</span>
        </div>
        <span className="font-mono tabular-nums">
          {updatedLabel ? `Last update ${updatedLabel}` : "Connecting…"}
        </span>
      </div>

      <div className="rounded-xl border border-border bg-panel p-3 sm:p-5 md:p-6">
        {loading && !hasBook ? (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4, 5, 6].map((row) => (
              <Skeleton key={row} className="h-6 w-full" />
            ))}
          </div>
        ) : error && !hasBook ? (
          <OrderBookError error="Unable to load order book" refetch={refetch} />
        ) : !hasBook ? (
          <p className="py-12 text-center text-sm text-slate-500">Waiting for the first active market…</p>
        ) : (
          <OrderBookPanel snapshot={activeSnapshot ?? orderBook[0]} />
        )}
      </div>
    </div>
  );
}
