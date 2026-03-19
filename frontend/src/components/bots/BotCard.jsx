import ActionChip from "../ui/ActionChip";
import {
  getBotEmoji, getTeamColor, shortName, providerLabel,
  formatDollar, formatPnl, formatPnlPct, pnl, pnlPct,
} from "../../lib/botUtils";

export default function BotCard({ bot, onSelect }) {
  const color    = getTeamColor(bot);
  const emoji    = getBotEmoji(bot.name);
  const p        = pnl(bot);
  const pPct     = pnlPct(bot);
  const isUp     = p >= 0;
  const pnlColor = isUp ? "#22C55E" : "#EF4444";

  return (
    <div
      onClick={() => onSelect(bot)}
      className="bg-panel border border-border rounded-xl cursor-pointer
                 hover:bg-[#16161F] transition-colors duration-150 overflow-hidden"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="px-5 py-4 space-y-3">

        {/* Row 1: emoji + name + provider tag + value */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xl leading-none">{emoji}</span>
            <div>
              <span className="font-semibold text-sm text-[#F1F5F9]">
                {shortName(bot.name)}
              </span>
              <span
                className="ml-2 text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
                style={{ color, backgroundColor: `${color}20` }}
              >
                {providerLabel(bot)}
              </span>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="font-mono font-bold text-base text-[#F1F5F9]">
              {formatDollar(bot.total_value)}
            </div>
            <div className="font-mono text-xs" style={{ color: pnlColor }}>
              {formatPnl(p)}&nbsp;({formatPnlPct(pPct)})
            </div>
          </div>
        </div>

        {/* Row 2: last decision */}
        {(bot.last_action || bot.last_ticker) && (
          <div className="flex items-center gap-2 text-xs text-[#64748B]">
            <span className="text-[#64748B] font-mono">Last:</span>
            {bot.last_action && <ActionChip action={bot.last_action} />}
            {bot.last_ticker && (
              <span className="font-mono font-bold text-[#F1F5F9]">{bot.last_ticker}</span>
            )}
            {bot.last_decision_at && (
              <span className="font-mono text-[#334155] ml-auto">
                {new Date(bot.last_decision_at).toLocaleTimeString("en-US", {
                  hour: "2-digit", minute: "2-digit", hour12: false,
                })}
              </span>
            )}
          </div>
        )}

        {/* Row 3: position count + arrow */}
        <div className="flex items-center justify-between">
          <span className="text-[#64748B] text-xs font-mono">
            {bot.position_count > 0
              ? `${bot.position_count} open position${bot.position_count !== 1 ? "s" : ""}`
              : "No open positions"}
          </span>
          <span className="text-[#334155] text-sm">→</span>
        </div>

      </div>
    </div>
  );
}
