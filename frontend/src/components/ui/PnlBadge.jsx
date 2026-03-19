/**
 * value: number (positive or negative P&L)
 * size: "sm" | "md"
 */
export default function PnlBadge({ value, size = "md" }) {
  const isPositive = value >= 0;
  const color      = isPositive ? "#22C55E" : "#EF4444";
  const sign       = isPositive ? "+" : "";
  const textSize   = size === "sm" ? "text-xs" : "text-sm";

  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(value));

  return (
    <span className={`font-mono font-semibold ${textSize}`} style={{ color }}>
      {sign}{formatted}
    </span>
  );
}
