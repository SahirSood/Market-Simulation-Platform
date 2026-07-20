import ActionChip from "../ui/ActionChip";

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function truncate(text, len = 80) {
  if (!text) return "n/a";
  return text.length > len ? `${text.slice(0, len)}...` : text;
}

function formatShares(value) {
  if (value == null) return "n/a";
  return Number(value).toLocaleString("en-US");
}

export default function DecisionTable({ reasoning }) {
  if (!reasoning?.length) {
    return (
      <p className="py-4 text-center font-mono text-xs text-[#64748B]">
        No decisions recorded yet
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] border-collapse text-xs">
        <thead>
          <tr className="font-mono text-[10px] uppercase tracking-wider text-[#334155]">
            <th className="py-2 pr-3 text-left">Time</th>
            <th className="py-2 pr-3 text-left">Action</th>
            <th className="py-2 pr-3 text-left">Ticker</th>
            <th className="py-2 pr-3 text-right">Qty</th>
            <th className="py-2 pr-3 text-right">Fill</th>
            <th className="py-2 pr-3 text-right">Price</th>
            <th className="py-2 pr-3 text-right">Conf</th>
            <th className="py-2 pr-3 text-right">Evidence</th>
            <th className="py-2 pr-3 text-left">News</th>
            <th className="py-2 text-left">Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {reasoning.map((r, i) => (
            <tr
              key={r.id ?? i}
              className={`border-t border-border ${i % 2 === 0 ? "bg-panel" : "bg-bg"}`}
            >
              <td className="whitespace-nowrap py-2.5 pr-3 font-mono text-[#64748B]">
                {formatTime(r.timestamp)}
              </td>
              <td className="py-2.5 pr-3">
                <ActionChip action={r.action} />
              </td>
              <td className="py-2.5 pr-3 font-mono font-bold text-[#F1F5F9]">
                {r.ticker ?? "n/a"}
              </td>
              <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[#F1F5F9]">
                {formatShares(r.quantity)}
              </td>
              <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[#F1F5F9]">
                {r.fill_qty_total ? `${formatShares(r.fill_qty_total)} / ${r.fill_count}` : "0"}
              </td>
              <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[#F1F5F9]">
                {r.fill_avg_price != null ? `$${r.fill_avg_price.toFixed(2)}` : "n/a"}
              </td>
              <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[#F1F5F9]">
                {r.confidence != null ? r.confidence.toFixed(2) : "n/a"}
              </td>
              <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[#F1F5F9]">
                {r.evidence_ids?.length ?? 0}
              </td>
              <td className="max-w-[180px] py-2.5 pr-3 text-[#94A3B8]">
                <span title={r.headline_used || ""}>{truncate(r.headline_used, 70)}</span>
              </td>
              <td className="max-w-[220px] py-2.5 italic text-[#64748B]">
                <span title={r.reasoning}>
                  {truncate(r.reasoning)}
                  {r.speculative ? " (speculative)" : ""}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
