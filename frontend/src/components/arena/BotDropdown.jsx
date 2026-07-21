const OPTIONS = [
  { value: "average", label: "Average" },
  { value: "bear", label: "\uD83D\uDC3B Bear" },
  { value: "degen", label: "\uD83C\uDFB0 Degen" },
  { value: "analyst", label: "\uD83D\uDD2C Analyst" },
  { value: "contrarian", label: "\uD83D\uDD04 Contrarian" },
  { value: "macro", label: "\uD83C\uDF0D Macro" },
];

export default function BotDropdown({ team, value, onChange }) {
  const isClaude = team === "claude";
  const label = isClaude ? "Claude" : "OpenAI";
  const color = isClaude ? "#2563EB" : "#F97316";

  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-mono font-bold uppercase tracking-widest" style={{ color }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer appearance-none rounded-full border border-border bg-white px-3 py-2 pr-8 text-sm font-medium text-slate-700 shadow-sm outline-none transition-colors hover:bg-slate-50"
        style={{
          borderColor: `${color}40`,
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 10px center",
        }}
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
