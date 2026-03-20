import DepthBar from "./DepthBar";

export default function OrderBookPanel({ snapshot }) {
  const asks = Array.isArray(snapshot?.asks) ? [...snapshot.asks].reverse() : [];
  const bids = Array.isArray(snapshot?.bids) ? snapshot.bids : [];
  const lowestAsk = snapshot?.asks?.[0]?.price;
  const highestBid = snapshot?.bids?.[0]?.price;
  const spread =
    lowestAsk != null && highestBid != null ? Math.max(lowestAsk - highestBid, 0) : null;
  const maxQuantity = Math.max(
    0,
    ...asks.map((level) => level.quantity ?? 0),
    ...bids.map((level) => level.quantity ?? 0)
  );

  return (
    <div className="space-y-3">
      <div>
        <div className="mb-2 px-3 text-[10px] font-mono font-bold tracking-widest text-[#EF4444]">
          ASKS
        </div>
        <div className="space-y-0.5">
          {asks.map((level, index) => (
            <DepthBar
              key={`ask-${level.price}-${index}`}
              side="ask"
              price={level.price}
              quantity={level.quantity}
              maxQuantity={maxQuantity}
            />
          ))}
        </div>
      </div>

      <div className="border-y border-border py-1 text-center font-mono text-xs text-[#64748B]">
        {spread != null ? `-- SPREAD $${spread.toFixed(2)} --` : "-- SPREAD -- --"}
      </div>

      <div>
        <div className="mb-2 px-3 text-[10px] font-mono font-bold tracking-widest text-[#3B82F6]">
          BIDS
        </div>
        <div className="space-y-0.5">
          {bids.map((level, index) => (
            <DepthBar
              key={`bid-${level.price}-${index}`}
              side="bid"
              price={level.price}
              quantity={level.quantity}
              maxQuantity={maxQuantity}
            />
          ))}
        </div>
      </div>

      <div className="mt-2 border-t border-border pt-2 font-mono text-xs text-[#64748B]">
        Last trade: ${Number(snapshot?.last_price ?? 0).toFixed(2)} | Total trades:{" "}
        {snapshot?.total_trades ?? 0} | Volume: {snapshot?.total_volume ?? 0}
      </div>
    </div>
  );
}
