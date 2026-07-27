export default function DepthBar({ side, price, quantity, orderCount = 0, maxQuantity, best = false }) {
  const width = maxQuantity > 0 ? Math.min((quantity / maxQuantity) * 100, 100) : 0;
  const isAsk = side === "ask";
  const barColor = isAsk ? "rgba(225, 29, 72, 0.09)" : "rgba(5, 150, 105, 0.09)";
  const priceColor = isAsk ? "text-rose-700" : "text-emerald-700";

  return (
    <div
      className={`relative overflow-hidden border-b border-slate-100 px-3 py-2.5 last:border-b-0 ${
        best ? "bg-slate-50" : "bg-white"
      }`}
      aria-label={`${quantity} shares across ${orderCount} order${orderCount === 1 ? "" : "s"} ${
        isAsk ? "offered for sale" : "bid for purchase"
      } at $${Number(price).toFixed(2)}`}
    >
      <div
        className={`absolute inset-y-0 transition-[width] duration-300 ease-out ${isAsk ? "right-0" : "left-0"}`}
        style={{ width: `${width}%`, backgroundColor: barColor }}
      />
      <div className="relative z-10 grid grid-cols-[1fr_auto] items-center gap-4">
        <span className={`font-mono text-sm font-semibold tabular-nums ${priceColor}`}>
          ${Number(price).toFixed(2)}
        </span>
        <div className="flex items-center gap-2 text-right">
          {best ? <span className="hidden text-[10px] font-semibold uppercase tracking-wide text-slate-400 sm:inline">Best</span> : null}
          <span className="min-w-20 text-right">
            <span className="block font-mono text-sm tabular-nums text-slate-700">
              {Number(quantity || 0).toLocaleString()}
            </span>
            {orderCount > 0 ? (
              <span className="block text-[10px] text-slate-400">
                {orderCount} {orderCount === 1 ? "order" : "orders"}
              </span>
            ) : null}
          </span>
        </div>
      </div>
    </div>
  );
}
