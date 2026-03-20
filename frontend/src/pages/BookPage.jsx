import { useEffect, useState } from "react";
import OrderBookPanel from "../components/book/OrderBookPanel";
import Skeleton from "../components/ui/Skeleton";
import { useOrderBook } from "../hooks/useOrderBook";

function OrderBookError({ error, refetch }) {
  return (
    <div className="flex items-center gap-3 bg-[#450A0A] border border-[#EF4444]/30 rounded-xl px-5 py-3 text-sm">
      <span className="text-[#EF4444]">{error}</span>
      <button onClick={refetch} className="text-[#EF4444] text-xs font-mono underline ml-auto">
        Retry
      </button>
    </div>
  );
}

export default function BookPage() {
  const { orderBook, loading, error, refetch } = useOrderBook();
  const [activeTicker, setActiveTicker] = useState("");

  useEffect(() => {
    if (!orderBook?.length) return;
    if (!activeTicker || !orderBook.some((snapshot) => snapshot.ticker === activeTicker)) {
      setActiveTicker(orderBook[0].ticker);
    }
  }, [orderBook, activeTicker]);

  const activeSnapshot = orderBook?.find((snapshot) => snapshot.ticker === activeTicker);

  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <h1 className="text-xl font-semibold text-[#F1F5F9]">ORDER BOOK</h1>

        <div className="flex flex-wrap gap-2">
          {(orderBook ?? []).map((snapshot) => {
            const isActive = snapshot.ticker === activeTicker;
            return (
              <button
                key={snapshot.ticker}
                onClick={() => setActiveTicker(snapshot.ticker)}
                className={`rounded-lg px-3 py-1 text-xs font-mono transition-colors ${
                  isActive
                    ? "bg-[#3B82F6] text-white"
                    : "bg-border text-[#64748B] hover:bg-[#16161F]"
                }`}
              >
                {snapshot.ticker}
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-panel border border-border rounded-xl p-6">
        {loading ? (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4, 5, 6].map((row) => (
              <Skeleton key={row} className="h-6 w-full" />
            ))}
          </div>
        ) : error ? (
          <OrderBookError error="Unable to load order book" refetch={refetch} />
        ) : !orderBook?.length ? (
          <p className="font-mono text-sm text-[#64748B]">Waiting for first orders...</p>
        ) : (
          <OrderBookPanel snapshot={activeSnapshot ?? orderBook[0]} />
        )}
      </div>
    </div>
  );
}
