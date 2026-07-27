import DepthBar from "./DepthBar";

function BookMetric({ label, value, detail }) {
  return (
    <div className="rounded-md border border-border bg-slate-50 px-4 py-3">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold tabular-nums text-ink">{value}</div>
      <div className="mt-0.5 text-xs text-slate-500">{detail}</div>
    </div>
  );
}

function BookSide({ side, levels, maxQuantity }) {
  const isAsk = side === "ask";
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-white">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">{isAsk ? "Sellers (asks)" : "Buyers (bids)"}</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {isAsk ? "Lowest price someone will sell for" : "Highest price someone will pay"}
            </p>
          </div>
          <span className={`h-2.5 w-2.5 rounded-full ${isAsk ? "bg-rose-500" : "bg-emerald-500"}`} />
        </div>
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-4 border-b border-border bg-slate-50 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
        <span>Price</span>
        <span className="pr-0.5 text-right">Shares waiting</span>
      </div>
      <div className="min-h-[184px]">
        {levels.length ? (
          levels.map((level, index) => (
            <DepthBar
              key={`${side}-${level.price}`}
              side={side}
              price={level.price}
              quantity={level.quantity}
              orderCount={level.order_count}
              maxQuantity={maxQuantity}
              best={index === 0}
            />
          ))
        ) : (
          <div className="flex min-h-[184px] items-center justify-center px-4 text-center text-sm text-slate-500">
            No {isAsk ? "sell" : "buy"} orders are waiting.
          </div>
        )}
      </div>
    </section>
  );
}

export default function OrderBookPanel({ snapshot }) {
  const asks = Array.isArray(snapshot?.asks) ? snapshot.asks.slice(0, 8) : [];
  const bids = Array.isArray(snapshot?.bids) ? snapshot.bids.slice(0, 8) : [];
  const lowestAsk = asks[0]?.price;
  const highestBid = bids[0]?.price;
  const spread =
    snapshot?.spread ??
    (lowestAsk != null && highestBid != null ? Math.max(lowestAsk - highestBid, 0) : null);
  const midpoint =
    snapshot?.mid_price ??
    (lowestAsk != null && highestBid != null ? (lowestAsk + highestBid) / 2 : null);
  const maxQuantity = Math.max(
    0,
    ...asks.map((level) => level.quantity ?? 0),
    ...bids.map((level) => level.quantity ?? 0)
  );

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <BookMetric
          label="Midpoint"
          value={midpoint != null ? `$${Number(midpoint).toFixed(2)}` : "—"}
          detail="Halfway between the best bid and ask"
        />
        <BookMetric
          label="Bid–ask spread"
          value={spread != null ? `$${Number(spread).toFixed(2)}` : "—"}
          detail="Gap between the closest buyer and seller"
        />
        <BookMetric
          label="Executed trades"
          value={Number(snapshot?.trade_count || 0).toLocaleString()}
          detail="Matches completed in this simulated market"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <BookSide side="bid" levels={bids} maxQuantity={maxQuantity} />
        <BookSide side="ask" levels={asks} maxQuantity={maxQuantity} />
      </div>

      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-slate-700">
        <span className="font-semibold text-slate-900">How to read the rows:</span> the number under “Shares waiting” is
        the large number is the total quantity queued at that exact price, while the smaller line shows how many
        orders make up that quantity. For example, <span className="font-mono font-semibold">500 · 1 order</span> means
        one simulated order for 500 shares—not a multiplier. The shaded bar only compares that quantity with the
        largest visible row.
      </div>
    </div>
  );
}
