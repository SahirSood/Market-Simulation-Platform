import ActionChip from "../ui/ActionChip";
import {
  formatDollar,
  formatPnl,
  formatPnlPct,
  getTeamColor,
  pnl,
  pnlPct,
  providerLabel,
  shortName,
} from "../../lib/botUtils";

export default function BotCard({ bot, onSelect }) {
  const color = getTeamColor(bot);
  const initials = shortName(bot.name).slice(0, 2).toUpperCase();
  const p = pnl(bot);
  const pPct = pnlPct(bot);
  const pnlColor = p >= 0 ? "#16A34A" : "#DC2626";

  return (
    <button
      type="button"
      onClick={() => onSelect(bot)}
      className="group w-full overflow-hidden rounded-lg border border-border bg-white text-left shadow-sm transition-colors duration-150 hover:border-slate-400"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="space-y-3 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-50 text-xs font-semibold tracking-wide text-slate-600 ring-1 ring-slate-200">
              {initials}
            </span>
            <div className="min-w-0">
              <div className="truncate text-base font-semibold text-ink">{shortName(bot.name)}</div>
              <span
                className="mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-mono font-bold"
                style={{ color, backgroundColor: `${color}14` }}
              >
                {providerLabel(bot)}
              </span>
            </div>
          </div>
          <div className="shrink-0 text-left sm:text-right">
            <div className="text-base font-semibold tabular-nums text-ink">{formatDollar(bot.total_value)}</div>
            <div className="font-mono text-xs font-semibold" style={{ color: pnlColor }}>
              {formatPnl(p)} ({formatPnlPct(pPct)})
            </div>
          </div>
        </div>

        {(bot.last_action || bot.last_ticker) && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-medium text-slate-500">Last</span>
            {bot.last_action && <ActionChip action={bot.last_action} />}
            {bot.last_ticker ? <span className="font-mono font-bold text-ink">{bot.last_ticker}</span> : null}
            {bot.last_decision_at ? (
              <span className="w-full font-mono text-slate-400 sm:ml-auto sm:w-auto">
                {new Date(bot.last_decision_at).toLocaleTimeString("en-US", {
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                })}
              </span>
            ) : null}
          </div>
        )}

        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-500">
            {bot.position_count > 0
              ? `${bot.position_count} open position${bot.position_count !== 1 ? "s" : ""}`
              : "No open positions"}
          </span>
          <span className="text-sm font-bold text-slate-300 transition-colors group-hover:text-slate-500">-&gt;</span>
        </div>
      </div>
    </button>
  );
}
