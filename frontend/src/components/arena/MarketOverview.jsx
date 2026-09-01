import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Skeleton from "../ui/Skeleton";
import { holdCauseLabel } from "../../lib/holdCauses";

const RANGES = [
  { id: "1m", label: "1M", points: 22 },
  { id: "3m", label: "3M", points: 64 },
  { id: "6m", label: "6M", points: 126 },
];
const COLORS = { SPY: "#64748B", QQQ: "#B95818" };

function percent(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  const number = Number(value) * 100;
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}%`;
}

function money(value) {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function mergeSeries(series, pointLimit) {
  const rows = new Map();
  series.forEach((item) => {
    const points = (item.points || []).slice(-pointLimit);
    const base = Number(points[0]?.price);
    points.forEach((point) => {
      const key = point.timestamp;
      if (!key) return;
      const row = rows.get(key) || { timestamp: key };
      const price = Number(point.price);
      row[item.ticker] = base && Number.isFinite(price) ? ((price - base) / base) * 100 : null;
      rows.set(key, row);
    });
  });
  return [...rows.values()].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-white px-3 py-2 text-xs shadow-lg">
      <div className="mb-2 font-mono text-slate-500">
        {new Date(label).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
      </div>
      {payload.map((item) => (
        <div key={item.dataKey} className="flex min-w-[150px] items-center justify-between gap-5 py-0.5">
          <span className="font-medium" style={{ color: item.color }}>{item.name}</span>
          <span className="font-mono text-slate-800">{item.value >= 0 ? "+" : ""}{Number(item.value).toFixed(2)}%</span>
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value, detail, tone = "text-ink" }) {
  return (
    <div className="min-w-0 border-r border-border px-4 py-3 last:border-r-0">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className={`mt-1 truncate text-lg font-semibold tabular-nums ${tone}`}>{value}</div>
      <div className="mt-0.5 truncate text-xs text-slate-500">{detail}</div>
    </div>
  );
}

function MarketRecap({ data }) {
  const recommendation = data?.recommendation;
  const views = (data?.agent_debate || []).slice(0, 6);
  return (
    <div className="border-t border-border bg-slate-50 px-4 py-4 sm:px-5">
      <div className="grid gap-5 xl:grid-cols-[1.1fr_1.9fr]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase text-slate-500">Market recap</span>
            {recommendation ? (
              <span className="rounded-full bg-white px-2 py-1 font-mono text-[10px] font-semibold text-slate-700 ring-1 ring-border">
                {recommendation.label} · {Math.round(Number(recommendation.confidence || 0) * 100)}% confidence
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{data?.so_what || "Waiting for enough market context to form a recap."}</p>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            {(data?.why_it_matters || []).slice(0, 2).map((item) => <span key={item}>• {item}</span>)}
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {views.length ? views.map((view, index) => (
            <div key={`${view.perspective}-${view.provider || index}`} className="border-l-2 border-slate-300 bg-white px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-semibold text-ink">{view.perspective} · {view.provider || "offline"}</span>
                <span className="font-mono text-[10px] font-semibold text-slate-500">{view.action || "n/a"}</span>
              </div>
              {view.action === "HOLD" && view.hold_cause ? <div className="mt-1 text-[10px] font-semibold uppercase text-slate-400">{holdCauseLabel(view.hold_cause)}</div> : null}
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{view.reasoning}</p>
            </div>
          )) : <div className="text-sm text-slate-500">Agent views will appear after the first decisions.</div>}
        </div>
      </div>
    </div>
  );
}

export default function MarketOverview({ data, ticker, onTickerChange, loading, error }) {
  const [range, setRange] = useState("6m");
  const rangeConfig = RANGES.find((item) => item.id === range) || RANGES[2];
  const series = data?.what_changed?.normalized_series || [];
  const chartData = useMemo(() => mergeSeries(series, rangeConfig.points), [series, rangeConfig.points]);
  const comparisons = data?.what_changed?.comparisons || [];
  const tickerPeriod = data?.what_changed?.ticker?.periods?.find((item) => item.period === range);
  const spy = comparisons.find((item) => item.period === range && item.benchmark === "SPY");
  const qqq = comparisons.find((item) => item.period === range && item.benchmark === "QQQ");
  const tickers = data?.universe?.tradable_tickers || ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA"];
  const lineTickers = [ticker, ...(data?.universe?.benchmark_tickers || ["SPY", "QQQ"])];

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-border px-4 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase text-slate-500">Market context · simulated execution</div>
          <h1 className="mt-1 text-2xl font-semibold text-ink sm:text-3xl">Market context</h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
            Inspect the selected name against SPY and QQQ after you have read the agent performance and decision tape.
          </p>
        </div>
        <div className="flex flex-wrap gap-1" aria-label="Tradable ticker">
          {tickers.map((symbol) => (
            <button
              key={symbol}
              type="button"
              onClick={() => onTickerChange(symbol)}
              className={`min-h-9 min-w-[54px] rounded-md px-2.5 font-mono text-xs font-semibold transition-colors ${ticker === symbol ? "bg-ink text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-ink"}`}
            >
              {symbol}
            </button>
          ))}
        </div>
      </div>

      {loading ? <div className="p-5"><Skeleton className="h-[390px]" /></div> : error ? (
        <div className="m-5 border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 border-b border-border sm:grid-cols-4">
            <Metric label={`${ticker} live price`} value={money(data?.current_prices?.[ticker]?.price)} detail={data?.what_changed?.as_of_time ? `history through ${new Date(data.what_changed.as_of_time).toLocaleDateString()}` : "live market feed"} />
            <Metric label={`${ticker} return`} value={percent(tickerPeriod?.return)} detail={rangeConfig.label} tone={Number(tickerPeriod?.return) >= 0 ? "text-emerald-700" : "text-rose-700"} />
            <Metric label="Excess vs SPY" value={percent(spy?.excess_return)} detail={`${rangeConfig.label} relative return`} tone={Number(spy?.excess_return) >= 0 ? "text-emerald-700" : "text-rose-700"} />
            <Metric label="Excess vs QQQ" value={percent(qqq?.excess_return)} detail={`${rangeConfig.label} relative return`} tone={Number(qqq?.excess_return) >= 0 ? "text-emerald-700" : "text-rose-700"} />
          </div>

          <div className="px-3 pb-3 pt-4 sm:px-5 sm:pb-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">Market return vs benchmarks</h2>
                <p className="mt-0.5 text-xs text-slate-500">Historical replay prices, rebased to 0% at the start of the selected window.</p>
              </div>
              <div className="flex rounded-md bg-slate-100 p-1">
                {RANGES.map((item) => (
                  <button key={item.id} type="button" onClick={() => setRange(item.id)} className={`min-h-8 rounded px-3 text-xs font-semibold ${range === item.id ? "bg-white text-ink shadow-sm" : "text-slate-500"}`}>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="h-[300px] w-full">
              {chartData.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 10, left: -14, bottom: 0 }}>
                    <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="timestamp" tickFormatter={(value) => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" })} tick={{ fill: "#64748B", fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={36} />
                    <YAxis tickFormatter={(value) => `${value}%`} tick={{ fill: "#64748B", fontSize: 11 }} tickLine={false} axisLine={false} width={55} />
                    <ReferenceLine y={0} stroke="#94A3B8" strokeDasharray="4 4" />
                    <Tooltip content={<ChartTooltip />} />
                    {lineTickers.map((symbol, index) => (
                      <Line key={symbol} dataKey={symbol} name={symbol} type="monotone" stroke={symbol === ticker ? "#087A55" : COLORS[symbol] || "#3157D5"} strokeWidth={symbol === ticker ? 3 : 2} strokeDasharray={symbol === ticker ? undefined : index === 1 ? "5 4" : "2 4"} dot={false} connectNulls isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : <div className="grid h-full place-items-center bg-slate-50 font-mono text-sm text-slate-500">No replay price history available.</div>}
            </div>
            <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
              {lineTickers.map((symbol, index) => <span key={symbol} className="flex items-center gap-2"><span className="h-0.5 w-5" style={{ backgroundColor: symbol === ticker ? "#087A55" : COLORS[symbol] || "#3157D5", opacity: index ? 0.75 : 1 }} />{symbol}</span>)}
            </div>
          </div>
          <MarketRecap data={data} />
        </>
      )}
    </section>
  );
}
