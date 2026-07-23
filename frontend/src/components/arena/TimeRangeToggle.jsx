const RANGES = ["1H", "6H", "1D", "7D", "30D", "All"];

export default function TimeRangeToggle({ value, onChange }) {
  return (
    <div className="flex w-full flex-wrap items-center gap-1 rounded-xl border border-border bg-white p-1 shadow-sm sm:w-auto sm:rounded-full">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={[
            "min-w-[48px] flex-1 rounded-full px-3 py-1 text-xs font-mono font-semibold transition-colors sm:flex-none",
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
