const STARTING_CASH = 100_000;

// Personality key → prefix that matches bot_id
const PERSONALITY_PREFIX = {
  bear:       "bear-001",
  degen:      "degen-001",
  analyst:    "analyst-001",
  contrarian: "contrarian-001",
  macro:      "macro-001",
};

/** Get time-series [{timestamp, value}] for a given team + selection */
export function getTeamSeries(bots, selection, reasoningMap, currentValues) {
  if (selection === "average") {
    const allSeries = bots.map((b) => reasoningMap.get(b.bot_id) || []);
    const currentMap = Object.fromEntries(bots.map((b) => [b.bot_id, b.total_value]));
    return averageSeries(allSeries, bots.map((b) => currentMap[b.bot_id]));
  }

  const prefix = PERSONALITY_PREFIX[selection];
  const bot = bots.find((b) => b.bot_id.startsWith(prefix));
  if (!bot) return [];

  const series = reasoningMap.get(bot.bot_id) || [];
  // Inject current live value as the latest point
  const now = new Date().toISOString();
  if (bot.total_value != null) {
    return [...series, { timestamp: now, value: bot.total_value }];
  }
  return series;
}

/** Average N time series with carry-forward. Each series: [{timestamp,value}] */
function averageSeries(allSeries, currentValues = []) {
  // Inject a "now" point for each series using current live value
  const now = new Date().toISOString();
  const augmented = allSeries.map((s, i) => {
    if (currentValues[i] != null) return [...s, { timestamp: now, value: currentValues[i] }];
    return s;
  });

  const allTimestamps = [
    ...new Set(augmented.flatMap((s) => s.map((p) => p.timestamp))),
  ].sort();

  if (!allTimestamps.length) return [];

  const lastVals = augmented.map(() => STARTING_CASH);
  const activeSeries = augmented.filter((s) => s.length > 0);
  if (!activeSeries.length) return [];

  return allTimestamps.map((ts) => {
    augmented.forEach((series, i) => {
      const pt = series.find((p) => p.timestamp === ts);
      if (pt) lastVals[i] = pt.value;
    });
    const count = augmented.filter((s) => s.length > 0).length || 1;
    const avg = lastVals.slice(0, augmented.length).reduce((a, b) => a + b, 0) / count;
    return { timestamp: ts, value: avg };
  });
}

const RANGE_MS = {
  "1D":  24 * 3600 * 1000,
  "7D":  7 * 24 * 3600 * 1000,
  "30D": 30 * 24 * 3600 * 1000,
  All:   Infinity,
};

/** Merge two time series into Recharts-ready [{time, claude, gpt}] */
export function buildChartData(claudeSeries, gptSeries, timeRange) {
  const cutoffMs = RANGE_MS[timeRange] ?? Infinity;
  const cutoff   = Date.now() - cutoffMs;

  const filter = (s) => s.filter((p) => new Date(p.timestamp).getTime() >= cutoff);
  const fc = filter(claudeSeries);
  const fg = filter(gptSeries);

  const allTs = [...new Set([...fc.map((p) => p.timestamp), ...fg.map((p) => p.timestamp)])].sort();
  if (!allTs.length) return [];

  const cMap = Object.fromEntries(fc.map((p) => [p.timestamp, p.value]));
  const gMap = Object.fromEntries(fg.map((p) => [p.timestamp, p.value]));

  let lastC = STARTING_CASH;
  let lastG = STARTING_CASH;

  return allTs.map((ts) => {
    if (cMap[ts] !== undefined) lastC = cMap[ts];
    if (gMap[ts] !== undefined) lastG = gMap[ts];
    return {
      time:   formatXLabel(ts, timeRange),
      rawTs:  ts,
      claude: Math.round(lastC),
      gpt:    Math.round(lastG),
    };
  });
}

function formatXLabel(isoTs, range) {
  const d = new Date(isoTs);
  if (range === "1D") {
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric" });
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
  const sign = v >= 0 ? "+" : "";
  return `${sign}${formatDollar(v)}`;
}

export function formatPnlPct(current, base = STARTING_CASH) {
  const pct = ((current - base) / base) * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}
