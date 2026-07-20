const RANGES = ["1H", "6H", "1D", "7D", "30D", "All"];

export default function TimeRangeToggle({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 bg-bg rounded-lg p-1 border border-border">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={[
            "px-3 py-1 text-xs font-mono font-semibold rounded-md transition-colors",
            value === r
              ? "bg-claude text-white"
              : "text-[#64748B] hover:text-[#F1F5F9]",
          ].join(" ")}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
