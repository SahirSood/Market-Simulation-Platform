const STYLES = {
  BUY:  "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  SELL: "bg-rose-50 text-rose-700 ring-1 ring-rose-200",
  HOLD: "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200",
};

export default function ActionChip({ action }) {
  const cls = STYLES[action] ?? STYLES.HOLD;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-mono font-bold tracking-wider ${cls}`}>
      {action}
    </span>
  );
}
