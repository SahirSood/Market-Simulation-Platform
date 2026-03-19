import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "../../hooks/useWebSocket";
import TeamDot     from "../ui/TeamDot";
import ActionChip  from "../ui/ActionChip";

// ── Helpers ───────────────────────────────────────────────────────────────────

const EMOJI_MAP = {
  bear:       "🐻",
  degen:      "🎰",
  analyst:    "🔬",
  contrarian: "🔄",
  macro:      "🌍",
};

function getBotEmoji(botName = "") {
  const lower = botName.toLowerCase();
  for (const [key, emoji] of Object.entries(EMOJI_MAP)) {
    if (lower.includes(key)) return emoji;
  }
  return "🤖";
}

function getProvider(event) {
  // derive from bot_id: "bear-001-claude" or "bear-001-openai"
  if (event.bot_id?.includes("claude")) return "claude";
  if (event.bot_id?.includes("openai")) return "openai";
  return "claude";
}

function formatTime(isoTs) {
  return new Date(isoTs).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function truncate(text, len = 90) {
  if (!text) return "";
  return text.length > len ? text.slice(0, len) + "…" : text;
}

// ── Feed item (with fade-in animation) ────────────────────────────────────────

function FeedItem({ event, isNew }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger fade-in on next tick
    const t = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(t);
  }, []);

  const provider = getProvider(event);
  const emoji    = getBotEmoji(event.bot_name);

  // Derive short display name: "BearBot (Claude)" → "Bear"
  const displayName = (event.bot_name || "")
    .replace(/Bot\s*/i, "")
    .replace(/\s*\(.*\)/, "")
    .trim();

  const providerLabel = provider === "claude" ? "Claude" : "OpenAI";

  return (
    <div
      className="flex items-start gap-3 py-3 border-b border-border last:border-b-0 transition-opacity duration-300"
      style={{ opacity: visible ? 1 : 0 }}
    >
      <TeamDot provider={provider} />

      <span className="text-base leading-none mt-0.5 select-none">{emoji}</span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-[#F1F5F9]">{displayName}</span>
          <span className="text-[#64748B] text-xs">({providerLabel})</span>
          <ActionChip action={event.action} />
          {event.ticker && (
            <span className="font-mono text-sm font-bold text-[#F1F5F9]">
              {event.ticker}
            </span>
          )}
          {event.quantity && (
            <span className="font-mono text-xs text-[#64748B]">×{event.quantity}</span>
          )}
          <span className="font-mono text-xs text-[#64748B] ml-auto shrink-0">
            {formatTime(event.timestamp)}
          </span>
        </div>
        {event.reasoning && (
          <p className="text-[#64748B] text-xs mt-1 italic leading-relaxed">
            &ldquo;{truncate(event.reasoning)}&rdquo;
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function LiveFeed() {
  const { events, connected } = useWebSocket();
  const containerRef = useRef(null);

  // Track which event IDs have been "seen" so we only animate truly new ones
  const seenRef = useRef(new Set());

  // Filter out heartbeats, keep trades and decisions
  const feedEvents = events.filter(
    (e) => e.type === "trade" || e.type === "decision"
  );

  // Scroll to top when new events arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [feedEvents.length]);

  return (
    <div className="bg-panel border border-border rounded-xl overflow-hidden">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-[#F1F5F9] font-semibold text-sm tracking-tight">
            LIVE FEED
          </span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              connected ? "bg-pnl-green animate-pulse" : "bg-[#64748B]"
            }`}
          />
        </div>
        <span className="text-[#64748B] text-xs font-mono">
          {feedEvents.length} events
        </span>
      </div>

      {/* Feed */}
      <div
        ref={containerRef}
        className="max-h-96 overflow-y-auto px-6"
      >
        {feedEvents.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-[#64748B] text-sm font-mono">
              Waiting for first trade…
            </p>
          </div>
        ) : (
          feedEvents.map((event, i) => {
            // Use timestamp + index as a stable key
            const key = `${event.timestamp}-${i}`;
            const isNew = !seenRef.current.has(key);
            if (isNew) seenRef.current.add(key);
            return <FeedItem key={key} event={event} isNew={isNew} />;
          })
        )}
      </div>

    </div>
  );
}
