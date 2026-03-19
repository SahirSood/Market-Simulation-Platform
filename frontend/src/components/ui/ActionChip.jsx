const STYLES = {
  BUY:  "bg-[#14532D] text-[#22C55E]",
  SELL: "bg-[#450A0A] text-[#EF4444]",
  HOLD: "bg-[#1E1B4B] text-[#818CF8]",
};

export default function ActionChip({ action }) {
  const cls = STYLES[action] ?? STYLES.HOLD;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider ${cls}`}>
      {action}
    </span>
  );
}
