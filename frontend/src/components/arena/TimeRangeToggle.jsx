const RANGES = ["1H", "6H", "1D", "7D", "30D", "All"];

export default function TimeRangeToggle({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-border bg-white p-1 shadow-sm">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={[
            "rounded-full px-3 py-1 text-xs font-mono font-semibold transition-colors",
            value === r
              ? "bg-claude text-white"
              : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
          ].join(" ")}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
