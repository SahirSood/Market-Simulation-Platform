import { useEffect } from "react";
import { useBotDetail }   from "../../hooks/useBotDetail";
import BotPnlChart        from "./BotPnlChart";
import DecisionTable      from "./DecisionTable";
import Skeleton           from "../ui/Skeleton";
import {
  getBotEmoji, getTeamColor, shortName, providerLabel,
  formatDollar, formatPnl, formatPnlPct, pnl, pnlPct,
} from "../../lib/botUtils";

function PositionRow({ pos }) {
  const upColor = pos.unrealized_pnl >= 0 ? "#22C55E" : "#EF4444";
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-b-0">
      <div className="flex items-center gap-3">
        <span className="font-mono font-bold text-sm text-[#F1F5F9] w-12">{pos.ticker}</span>
        <span className="font-mono text-xs text-[#64748B]">
          {pos.quantity > 0 ? "+" : ""}{pos.quantity} shares
        </span>
        <span className="font-mono text-xs text-[#64748B]">
          avg ${pos.avg_cost.toFixed(2)}
        </span>
      </div>
      <div className="text-right">
        <div className="font-mono text-sm text-[#F1F5F9]">
          ${pos.current_price.toFixed(2)}
        </div>
        <div className="font-mono text-xs" style={{ color: upColor }}>
          {formatPnl(pos.unrealized_pnl)}
        </div>
      </div>
    </div>
  );
}

export default function BotDrawer({ bot, onClose }) {
  const isOpen = bot != null;
  const { detail, reasoning, loading } = useBotDetail(bot?.bot_id ?? null);

  const color   = getTeamColor(bot);
  const p       = pnl(bot);
  const pPct    = pnlPct(bot);
  const pnlColor = p >= 0 ? "#22C55E" : "#EF4444";
  const latest = reasoning?.[0] ?? null;

  // Close on Escape key
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/50 z-[60] transition-opacity duration-250"
        style={{ opacity: isOpen ? 1 : 0, pointerEvents: isOpen ? "auto" : "none" }}
      />

      {/* Drawer panel */}
      <div
        className="fixed right-0 top-0 h-full w-[480px] bg-panel border-l border-border z-[70]
                   flex flex-col transition-transform duration-250 ease-out overflow-hidden"
        style={{ transform: isOpen ? "translateX(0)" : "translateX(100%)" }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0"
          style={{ borderLeft: `3px solid ${color}` }}
        >
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="text-[#64748B] hover:text-[#F1F5F9] text-lg leading-none mr-1"
            >
              ✕
            </button>
            <span className="text-xl">{getBotEmoji(bot?.name)}</span>
            <span className="font-semibold text-[#F1F5F9]">{shortName(bot?.name)}</span>
            <span
              className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{ color, backgroundColor: `${color}20` }}
            >
              {providerLabel(bot)}
            </span>
          </div>
          <div className="text-right">
            <div className="font-mono font-bold text-[#F1F5F9]">
              {formatDollar(bot?.total_value)}
            </div>
            <div className="font-mono text-xs" style={{ color: pnlColor }}>
              {formatPnl(p)}&nbsp;({formatPnlPct(pPct)})
            </div>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">

          {/* P&L Chart */}
          <div className="px-6 pt-5 pb-3">
            <h3 className="text-[10px] font-mono font-bold text-[#334155] uppercase tracking-widest mb-3">
              Portfolio Value
            </h3>
            {loading ? (
              <Skeleton className="h-[180px] w-full" />
            ) : (
              <BotPnlChart reasoning={reasoning} color={color} />
            )}
          </div>

          <div className="border-t border-border" />

          {/* Positions */}
          <div className="px-6 pt-4 pb-3">
            <h3 className="text-[10px] font-mono font-bold text-[#334155] uppercase tracking-widest mb-3">
              Positions
            </h3>
            {loading ? (
              <div className="space-y-2">
                {[1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : detail?.positions?.length ? (
              detail.positions.map((pos) => (
                <PositionRow key={pos.ticker} pos={pos} />
              ))
            ) : (
              <p className="text-[#64748B] text-xs font-mono py-2">No open positions</p>
            )}
          </div>

          <div className="border-t border-border" />

          {/* Decision history */}
          <div className="px-6 pt-4 pb-6">
            <h3 className="text-[10px] font-mono font-bold text-[#334155] uppercase tracking-widest mb-3">
              Decision History
            </h3>
            {!loading && latest?.evidence_urls?.length ? (
              <div className="mb-3 rounded border border-border bg-bg p-2">
                <p className="text-[10px] font-mono uppercase tracking-wider text-[#334155] mb-1">
                  Latest Evidence Citations
                </p>
                <div className="space-y-1">
                  {latest.evidence_urls.slice(0, 3).map((url, idx) => (
                    <a
                      key={`${url}-${idx}`}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="block text-[11px] font-mono text-[#60A5FA] hover:underline truncate"
                      title={url}
                    >
                      {url}
                    </a>
                  ))}
                </div>
              </div>
            ) : null}
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-8 w-full" />)}
              </div>
            ) : (
              <DecisionTable reasoning={reasoning} />
            )}
          </div>

        </div>
      </div>
    </>
  );
}
