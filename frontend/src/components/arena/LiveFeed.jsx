import { useEffect, useRef, useState } from "react";
import { getTrades } from "../../api/endpoints";
import { useWebSocket } from "../../hooks/useWebSocket";
import ActionChip from "../ui/ActionChip";
import TeamDot from "../ui/TeamDot";

const BOT_TAGS = {
  bear: "BE",
  degen: "DG",
  analyst: "AN",
  contrarian: "CT",
  macro: "MC",
};

function getBotTag(botName = "") {
  const lower = botName.toLowerCase();
  for (const [key, tag] of Object.entries(BOT_TAGS)) {
    if (lower.includes(key)) return tag;
  }
  return "AI";
}

function getProvider(event) {
  if (event.bot_id?.includes("claude")) return "claude";
  if (event.bot_id?.includes("openai")) return "openai";
  return "claude";
}

function formatTime(isoTs) {
  if (!isoTs) return "";
  return new Date(isoTs).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function truncate(text, len = 110) {
  if (!text) return "";
  return text.length > len ? `${text.slice(0, len)}...` : text;
}

function FeedItem({ event }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const provider = getProvider(event);
  const tag = getBotTag(event.bot_name);
  const displayName = (event.bot_name || "")
    .replace(/Bot\s*/i, "")
    .replace(/\s*\(.*\)/, "")
    .trim();
  const providerLabel = provider === "claude" ? "Claude" : "OpenAI";
  const filled = Number(event.fill_qty_total || 0) > 0;

  return (
    <div
      className="flex items-start gap-3 border-b border-border py-3 transition-opacity duration-300 last:border-b-0"
      style={{ opacity: visible ? 1 : 0 }}
    >
      <TeamDot provider={provider} />
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border bg-bg font-mono text-[10px] font-bold text-[#CBD5E1]">
        {tag}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-[#F1F5F9]">{displayName || "Bot"}</span>
          <span className="text-xs text-[#64748B]">({providerLabel})</span>
          <ActionChip action={event.action} />
          {event.ticker ? (
            <span className="font-mono text-sm font-bold text-[#F1F5F9]">{event.ticker}</span>
          ) : null}
          {event.quantity ? (
            <span className="font-mono text-xs text-[#64748B]">x{event.quantity}</span>
          ) : null}
          {filled ? (
            <span className="rounded bg-[#14532D] px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#86EFAC]">
              FILLED {event.fill_qty_total}
            </span>
          ) : null}
          <span className="ml-auto shrink-0 font-mono text-xs text-[#64748B]">
            {formatTime(event.timestamp)}
          </span>
        </div>
        {event.reasoning ? (
          <p className="mt-1 text-xs italic leading-relaxed text-[#64748B]">
            "{truncate(event.reasoning)}"
          </p>
        ) : null}
      </div>
    </div>
  );
}

export default function LiveFeed() {
  const { events, connected } = useWebSocket();
  const [recentEvents, setRecentEvents] = useState([]);
  const containerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function loadRecent() {
      const rows = await getTrades();
      if (cancelled) return;
      const mapped = (Array.isArray(rows) ? rows : []).map((row) => ({
        ...row,
        type: row.fill_qty_total > 0 ? "trade" : "decision",
      }));
      setRecentEvents(mapped);
    }

    loadRecent();
    const timer = setInterval(loadRecent, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const socketEvents = events.filter((event) => event.type === "trade" || event.type === "decision");
  const seen = new Set();
  const feedEvents = [...socketEvents, ...recentEvents]
    .filter((event) => {
      const key = event.id || `${event.timestamp}-${event.bot_id}-${event.action}-${event.ticker || ""}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 50);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [feedEvents.length]);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold tracking-tight text-[#F1F5F9]">Live Activity</span>
          <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-pnl-green animate-pulse" : "bg-[#64748B]"}`} />
        </div>
        <span className="font-mono text-xs text-[#64748B]">{feedEvents.length} events</span>
      </div>

      <div ref={containerRef} className="max-h-96 overflow-y-auto px-6">
        {feedEvents.length === 0 ? (
          <div className="py-12 text-center">
            <p className="font-mono text-sm text-[#64748B]">Waiting for first trade...</p>
          </div>
        ) : (
          feedEvents.map((event, index) => {
            const key = event.id || `${event.timestamp}-${index}`;
            return <FeedItem key={key} event={event} />;
          })
        )}
      </div>
    </div>
  );
}
