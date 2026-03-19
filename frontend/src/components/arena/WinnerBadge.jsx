import { formatDollar } from "../../lib/chartUtils";

/**
 * claudeVal / gptVal: current portfolio value for each side
 */
export default function WinnerBadge({ claudeVal, gptVal }) {
  if (claudeVal == null || gptVal == null) return null;

  const diff = Math.abs(claudeVal - gptVal);

  if (diff < 1) {
    return (
      <div className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold text-[#64748B] bg-[#1E1E2E]">
        TIED
      </div>
    );
  }

  const claudeLeading = claudeVal > gptVal;
  const color   = claudeLeading ? "#3B82F6" : "#F97316";
  const label   = claudeLeading ? "CLAUDE LEADING" : "GPT LEADING";

  return (
    <div
      className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold"
      style={{
        color,
        backgroundColor: `${color}26`, // 15% opacity
      }}
    >
      {label} +{formatDollar(diff)}
    </div>
  );
}
