import { useEffect } from "react";
import { useBotDetail } from "../../hooks/useBotDetail";
import BotPnlChart from "./BotPnlChart";
import DecisionTable from "./DecisionTable";
import Skeleton from "../ui/Skeleton";
import {
  formatDollar,
  formatPnl,
  formatPnlPct,
  getBotEmoji,
  getTeamColor,
  pnl,
  pnlPct,
  providerLabel,
  shortName,
} from "../../lib/botUtils";

function PositionRow({ pos }) {
  const upColor = pos.unrealized_pnl >= 0 ? "#16A34A" : "#DC2626";
  return (
    <div className="flex items-center justify-between border-b border-border py-2.5 last:border-b-0">
      <div className="flex items-center gap-3">
        <span className="w-12 font-mono text-sm font-bold text-ink">{pos.ticker}</span>
        <span className="font-mono text-xs text-slate-500">
          {pos.quantity > 0 ? "+" : ""}
          {pos.quantity} shares
        </span>
        <span className="font-mono text-xs text-slate-500">avg ${pos.avg_cost.toFixed(2)}</span>
      </div>
      <div className="text-right">
        <div className="font-mono text-sm text-ink">${pos.current_price.toFixed(2)}</div>
        <div className="font-mono text-xs font-semibold" style={{ color: upColor }}>
          {formatPnl(pos.unrealized_pnl)}
        </div>
      </div>
    </div>
  );
}

export default function BotDrawer({ bot, onClose }) {
  const isOpen = bot != null;
  const { detail, reasoning, loading } = useBotDetail(bot?.bot_id ?? null);

  const color = getTeamColor(bot);
  const p = pnl(bot);
  const pPct = pnlPct(bot);
  const pnlColor = p >= 0 ? "#16A34A" : "#DC2626";
  const latest = reasoning?.[0] ?? null;

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-[60] bg-slate-900/20 backdrop-blur-sm transition-opacity duration-200"
        style={{ opacity: isOpen ? 1 : 0, pointerEvents: isOpen ? "auto" : "none" }}
      />

      <aside
        className="fixed right-0 top-0 z-[70] flex h-full w-full max-w-[520px] flex-col overflow-hidden border-l border-border bg-white shadow-2xl shadow-slate-400/30 transition-transform duration-200 ease-out"
        style={{ transform: isOpen ? "translateX(0)" : "translateX(100%)" }}
      >
        <div className="shrink-0 border-b border-border px-6 py-4" style={{ borderTop: `4px solid ${color}` }}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <button
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-sm font-bold text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                aria-label="Close bot detail"
              >
                x
              </button>
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-50 text-xl ring-1 ring-slate-200">
                {getBotEmoji(bot?.name)}
              </span>
              <div className="min-w-0">
                <div className="truncate text-lg font-black text-ink">{shortName(bot?.name)}</div>
                <span
                  className="mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-mono font-bold"
                  style={{ color, backgroundColor: `${color}14` }}
                >
                  {providerLabel(bot)}
                </span>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="font-mono text-lg font-black text-ink">{formatDollar(bot?.total_value)}</div>
              <div className="font-mono text-xs font-semibold" style={{ color: pnlColor }}>
                {formatPnl(p)} ({formatPnlPct(pPct)})
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-5">
            <h3 className="mb-3 text-[10px] font-mono font-bold uppercase tracking-widest text-slate-500">
              Portfolio Value
            </h3>
            {loading ? (
              <Skeleton className="h-[180px] w-full rounded-2xl" />
            ) : (
              <BotPnlChart reasoning={reasoning} color={color} currentValue={bot?.total_value} />
            )}
          </div>

          <div className="border-t border-border" />

          <div className="px-6 py-4">
            <h3 className="mb-3 text-[10px] font-mono font-bold uppercase tracking-widest text-slate-500">
              Positions
            </h3>
            {loading ? (
              <div className="space-y-2">
                {[1, 2].map((i) => (
                  <Skeleton key={i} className="h-10 w-full rounded-xl" />
                ))}
              </div>
            ) : detail?.positions?.length ? (
              detail.positions.map((pos) => <PositionRow key={pos.ticker} pos={pos} />)
            ) : (
              <p className="py-2 text-xs font-mono text-slate-500">No open positions</p>
            )}
          </div>

          <div className="border-t border-border" />

          <div className="px-6 py-5">
            <h3 className="mb-3 text-[10px] font-mono font-bold uppercase tracking-widest text-slate-500">
              Decision History
            </h3>
            {!loading && latest?.evidence_urls?.length ? (
              <div className="mb-3 rounded-2xl border border-blue-100 bg-blue-50 p-3">
                <p className="mb-1 text-[10px] font-mono uppercase tracking-wider text-blue-700">
                  Latest SEC evidence
                </p>
                <div className="space-y-1">
                  {latest.evidence_urls.slice(0, 3).map((url, idx) => (
                    <a
                      key={`${url}-${idx}`}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="block truncate text-[11px] font-mono text-blue-700 hover:underline"
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
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-8 w-full rounded-xl" />
                ))}
              </div>
            ) : (
              <DecisionTable reasoning={reasoning} />
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
