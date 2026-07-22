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

function decisionOutcome(row) {
  const reasoning = String(row.reasoning || "").toLowerCase();
  if (Number(row.fill_qty_total || 0) > 0) {
    return {
      label: `executed ${formatShares(row.fill_qty_total)} / ${row.fill_count || 1}`,
      className: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    };
  }
  if (reasoning.includes("risk check rejected")) {
    return {
      label: "rejected",
      className: "bg-rose-50 text-rose-700 ring-rose-200",
    };
  }
  if (String(row.action || "").toUpperCase() === "HOLD") {
    return {
      label: "held",
      className: "bg-slate-100 text-slate-600 ring-slate-200",
    };
  }
  return {
    label: "submitted",
    className: "bg-blue-50 text-blue-700 ring-blue-200",
  };
}

export default function DecisionTable({ reasoning }) {
  if (!reasoning?.length) {
    return (
      <p className="py-4 text-center font-mono text-xs text-slate-500">
        No decisions recorded yet
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] border-collapse text-xs">
        <thead>
          <tr className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
            <th className="py-2 pr-3 text-left">Time</th>
            <th className="py-2 pr-3 text-left">Action</th>
            <th className="py-2 pr-3 text-left">Ticker</th>
            <th className="py-2 pr-3 text-right">Qty</th>
            <th className="py-2 pr-3 text-left">Outcome</th>
            <th className="py-2 pr-3 text-right">Price</th>
            <th className="py-2 pr-3 text-right">Conf</th>
            <th className="py-2 pr-3 text-right">Evidence</th>
            <th className="py-2 pr-3 text-left">News</th>
            <th className="py-2 text-left">Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {reasoning.map((r, i) => {
            const outcome = decisionOutcome(r);
            return (
              <tr
                key={r.id ?? i}
                className={`border-t border-border ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}
              >
                <td className="whitespace-nowrap py-2.5 pr-3 font-mono text-slate-500">
                  {formatTime(r.timestamp)}
                </td>
                <td className="py-2.5 pr-3">
                  <ActionChip action={r.action} />
                </td>
                <td className="py-2.5 pr-3 font-mono font-bold text-ink">
                  {r.ticker ?? "n/a"}
                </td>
                <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-slate-700">
                  {formatShares(r.quantity)}
                </td>
                <td className="whitespace-nowrap py-2.5 pr-3">
                  <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-bold ring-1 ${outcome.className}`}>
                    {outcome.label}
                  </span>
                </td>
                <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-slate-700">
                  {r.fill_avg_price != null ? `$${r.fill_avg_price.toFixed(2)}` : "n/a"}
                </td>
                <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-slate-700">
                  {r.confidence != null ? r.confidence.toFixed(2) : "n/a"}
                </td>
                <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-slate-700">
                  {r.evidence_ids?.length ?? 0}
                </td>
                <td className="max-w-[180px] py-2.5 pr-3 text-slate-600">
                  <span title={r.headline_used || ""}>{truncate(r.headline_used, 70)}</span>
                </td>
                <td className="max-w-[220px] py-2.5 text-slate-500">
                  <span title={r.reasoning}>
                    {truncate(r.reasoning)}
                    {r.speculative ? " (speculative)" : ""}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
