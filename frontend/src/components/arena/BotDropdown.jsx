const OPTIONS = [
  { value: "average",    label: "Average"          },
  { value: "bear",       label: "🐻 Bear"           },
  { value: "degen",      label: "🎰 Degen"          },
  { value: "analyst",    label: "🔬 Analyst"        },
  { value: "contrarian", label: "🔄 Contrarian"     },
  { value: "macro",      label: "🌍 Macro"          },
];

/**
 * team: "claude" | "gpt"
 * value: one of OPTIONS[*].value
 * onChange: (value) => void
 */
export default function BotDropdown({ team, value, onChange }) {
  const isClaude = team === "claude";
  const label    = isClaude ? "CLAUDE" : "GPT-4o";
  const color    = isClaude ? "#3B82F6" : "#F97316";

  return (
    <div className="flex flex-col gap-1">
      <span
        className="text-[10px] font-mono font-bold tracking-widest"
        style={{ color }}
      >
        {label}
      </span>
      <div
        className="rounded-lg overflow-hidden"
        style={{ borderLeft: `3px solid ${color}` }}
      >
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="bg-border text-[#F1F5F9] rounded-r-lg px-3 py-2 text-sm font-mono
                     appearance-none outline-none cursor-pointer
                     hover:bg-[#2A2A3E] transition-colors pr-8"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
            backgroundRepeat: "no-repeat",
            backgroundPosition: "right 10px center",
          }}
        >
          {OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
