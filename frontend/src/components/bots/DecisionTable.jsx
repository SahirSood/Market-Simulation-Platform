import ActionChip from "../ui/ActionChip";

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString("en-US", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

function truncate(text, len = 80) {
  if (!text) return "—";
  return text.length > len ? text.slice(0, len) + "…" : text;
}

export default function DecisionTable({ reasoning }) {
  if (!reasoning?.length) {
    return (
      <p className="text-[#64748B] text-xs font-mono py-4 text-center">
        No decisions recorded yet
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="text-[#334155] font-mono text-[10px] uppercase tracking-wider">
            <th className="text-left py-2 pr-3">Time</th>
            <th className="text-left py-2 pr-3">Action</th>
            <th className="text-left py-2 pr-3">Ticker</th>
            <th className="text-right py-2 pr-3">Price</th>
            <th className="text-right py-2 pr-3">Conf</th>
            <th className="text-right py-2 pr-3">Evidence</th>
            <th className="text-left py-2">Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {reasoning.map((r, i) => (
            <tr
              key={r.id ?? i}
              className={`border-t border-border ${i % 2 === 0 ? "bg-panel" : "bg-bg"}`}
            >
              <td className="py-2.5 pr-3 font-mono text-[#64748B] whitespace-nowrap">
                {formatTime(r.timestamp)}
              </td>
              <td className="py-2.5 pr-3">
                <ActionChip action={r.action} />
              </td>
              <td className="py-2.5 pr-3 font-mono font-bold text-[#F1F5F9]">
                {r.ticker ?? "—"}
              </td>
              <td className="py-2.5 pr-3 font-mono text-[#F1F5F9] text-right whitespace-nowrap">
                {r.fill_avg_price != null
                  ? `$${r.fill_avg_price.toFixed(2)}`
                  : "—"}
              </td>
              <td className="py-2.5 pr-3 font-mono text-[#F1F5F9] text-right whitespace-nowrap">
                {r.confidence != null ? r.confidence.toFixed(2) : "—"}
              </td>
              <td className="py-2.5 pr-3 font-mono text-[#F1F5F9] text-right whitespace-nowrap">
                {r.evidence_ids?.length ?? 0}
              </td>
              <td className="py-2.5 text-[#64748B] italic max-w-[180px]">
                <span title={r.reasoning}>
                  {truncate(r.reasoning)}{r.speculative ? " (speculative)" : ""}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
