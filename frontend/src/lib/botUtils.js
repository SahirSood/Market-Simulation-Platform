export const EMOJI_MAP = {
  bear:       "🐻",
  degen:      "🎰",
  analyst:    "🔬",
  contrarian: "🔄",
  macro:      "🌍",
};

export function getBotEmoji(nameOrId = "") {
  const s = nameOrId.toLowerCase();
  for (const [key, emoji] of Object.entries(EMOJI_MAP)) {
    if (s.includes(key)) return emoji;
  }
  return "🤖";
}

export function getTeamColor(bot) {
  return bot?.llm_provider === "claude" ? "#3B82F6" : "#F97316";
}

/** "BearBot (Claude)" → "Bear" */
export function shortName(fullName = "") {
  return fullName.replace(/Bot\s*/i, "").replace(/\s*\(.*\)/, "").trim();
}

/** "BearBot (Claude)" → "Claude" | "OpenAI" */
export function providerLabel(bot) {
  return bot?.llm_provider === "claude" ? "Claude" : "OpenAI";
}

export function startingCashFor(bot, fallback = 100_000) {
  return Number(bot?.starting_cash ?? fallback);
}

export function pnl(bot, startingCash = null) {
  const base = Number(startingCash ?? startingCashFor(bot));
  return (bot?.total_value ?? base) - base;
}

export function pnlPct(bot, startingCash = null) {
  const base = Number(startingCash ?? startingCashFor(bot));
  return (pnl(bot, base) / base) * 100;
}

export function formatDollar(v) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(v);
}

export function formatPnl(v) {
  return `${v >= 0 ? "+" : ""}${formatDollar(v)}`;
}

export function formatPnlPct(v) {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
