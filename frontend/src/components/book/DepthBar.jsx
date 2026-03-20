export default function DepthBar({ side, price, quantity, maxQuantity }) {
  const width = maxQuantity > 0 ? Math.min((quantity / maxQuantity) * 100, 100) : 0;
  const barColor = side === "ask" ? "rgba(239, 68, 68, 0.15)" : "rgba(59, 130, 246, 0.15)";

  return (
    <div className="relative overflow-hidden px-3 py-1.5 transition-colors hover:bg-[#16161F]">
      <div
        className="absolute inset-y-0 left-0"
        style={{ width: `${width}%`, backgroundColor: barColor }}
      />
      <div className="relative z-10 flex items-center justify-end gap-4">
        <span className="w-24 text-right font-mono text-sm text-[#F1F5F9]">
          ${Number(price).toFixed(2)}
        </span>
        <span className="w-20 text-right font-mono text-sm text-[#64748B]">
          x{quantity}
        </span>
      </div>
    </div>
  );
}
