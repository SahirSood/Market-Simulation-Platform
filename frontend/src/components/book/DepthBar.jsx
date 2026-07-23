export default function DepthBar({ side, price, quantity, maxQuantity }) {
  const width = maxQuantity > 0 ? Math.min((quantity / maxQuantity) * 100, 100) : 0;
  const barColor = side === "ask" ? "rgba(239, 68, 68, 0.15)" : "rgba(59, 130, 246, 0.15)";

  return (
    <div className="relative overflow-hidden px-2 py-1.5 transition-colors hover:bg-slate-100 sm:px-3">
      <div
        className="absolute inset-y-0 left-0"
        style={{ width: `${width}%`, backgroundColor: barColor }}
      />
      <div className="relative z-10 flex items-center justify-end gap-2 sm:gap-4">
        <span className="w-20 text-right font-mono text-sm text-ink sm:w-24">
          ${Number(price).toFixed(2)}
        </span>
        <span className="w-16 text-right font-mono text-sm text-slate-500 sm:w-20">
          x{quantity}
        </span>
      </div>
    </div>
  );
}
