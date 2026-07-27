import { useEffect, useRef, useState } from "react";
import { getTrades } from "../../api/endpoints";
import { useWebSocket } from "../../hooks/useWebSocket";
import ActionChip from "../ui/ActionChip";
import InfoTooltip from "../ui/InfoTooltip";
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
  return "--";
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

function truncate(text, len = 90) {
  if (!text) return "";
  return text.length > len ? `${text.slice(0, len)}...` : text;
}

function eventIdentity(event) {
  return String(
    event.id ||
      [
        event.timestamp,
        event.bot_id,
        event.action,
        event.ticker || "",
        event.quantity || "",
        event.order_id || "",
      ].join("-")
  );
}

function outcome(event) {
  const action = String(event.action || "").toUpperCase();
  const reasoning = String(event.reasoning || "").toLowerCase();
  if (Number(event.fill_qty_total || 0) > 0) {
    return {
      label: `executed ${event.fill_qty_total}`,
      className: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    };
  }
  if (reasoning.includes("risk check rejected")) {
    return {
      label: "rejected",
      className: "bg-rose-50 text-rose-700 ring-rose-200",
    };
  }
  if (action === "HOLD") {
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

function FeedItem({ event }) {
  const provider = getProvider(event);
  const tag = getBotTag(event.bot_name);
  const displayName = (event.bot_name || "")
    .replace(/Bot\s*/i, "")
    .replace(/\s*\(.*\)/, "")
    .trim();
  const providerLabel = provider === "claude" ? "Claude" : "OpenAI";
  const outcomePill = outcome(event);

  return (
    <div className="flex items-start gap-2 border-b border-border py-3 last:border-b-0 sm:gap-3">
      <TeamDot provider={provider} />
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border bg-slate-50 font-mono text-[10px] font-bold text-slate-600 sm:h-8 sm:w-8">
        {tag}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-bold text-ink">{displayName || "Bot"}</span>
          <span className="text-xs text-slate-500">({providerLabel})</span>
          <ActionChip action={event.action} />
          {event.ticker ? <span className="font-mono text-sm font-bold text-ink">{event.ticker}</span> : null}
          {event.quantity ? <span className="font-mono text-xs text-slate-500">x{event.quantity}</span> : null}
          <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-bold ring-1 ${outcomePill.className}`}>
            {outcomePill.label}
          </span>
          <span className="w-full shrink-0 font-mono text-xs text-slate-400 sm:ml-auto sm:w-auto">
            {formatTime(event.timestamp)}
          </span>
        </div>
        {event.reasoning ? (
          <p className="mt-1 text-xs leading-relaxed text-slate-600">
            {truncate(event.reasoning)}
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
      const key = eventIdentity(event);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 12);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [feedEvents.length]);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight text-ink">Live decision tape</h2>
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-pnl-green" : "bg-slate-300"}`} />
            <InfoTooltip label="What appears in the live tape?">
              Each row is a public event from the arena: a model proposal, HOLD, risk rejection, submitted order, or
              fill. Rationales are short public summaries, not hidden chain-of-thought.
            </InfoTooltip>
          </div>
          <p className="mt-1 text-sm text-slate-600">Proposals, risk rejections, fills, and concise rationales.</p>
        </div>
        <span className="w-fit text-xs font-medium tabular-nums text-slate-500">
          {feedEvents.length} events
        </span>
      </div>

      <div ref={containerRef} className="max-h-[340px] overflow-y-auto px-4 sm:px-6">
        {feedEvents.length === 0 ? (
          <div className="py-12 text-center">
            <p className="font-mono text-sm text-slate-500">Waiting for first arena event...</p>
          </div>
        ) : (
          feedEvents.map((event) => <FeedItem key={eventIdentity(event)} event={event} />)
        )}
      </div>
    </section>
  );
}
