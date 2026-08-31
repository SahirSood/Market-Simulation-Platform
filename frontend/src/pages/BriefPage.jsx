import { useEffect, useMemo, useState } from "react";
import { getDecisionBrief } from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";

const DEFAULT_TICKERS = ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA"];

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const number = Number(value) * 100;
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function price(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function dateLabel(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString();
}

function toneForReturn(value) {
  if (value === null || value === undefined) return "text-slate-500";
  return Number(value) >= 0 ? "text-emerald-700" : "text-rose-700";
}

function categoryTone(category) {
  if (category === "add") return "border-emerald-300 bg-emerald-50 text-emerald-800";
  if (category === "reduce") return "border-rose-300 bg-rose-50 text-rose-800";
  if (category === "wait") return "border-amber-300 bg-amber-50 text-amber-800";
  return "border-blue-300 bg-blue-50 text-blue-800";
}

function TrendPanel({ data }) {
  const periods = data?.what_changed?.ticker?.periods || [];
  const comparisons = data?.what_changed?.comparisons || [];
  return (
    <section className="border border-border bg-panel">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">What Changed</h2>
        <p className="mt-1 text-xs text-slate-500">
          Replay-window trend context as of {dateLabel(data?.what_changed?.as_of_time)}
        </p>
      </div>
      <div className="grid grid-cols-1 divide-y divide-border md:grid-cols-3 md:divide-x md:divide-y-0">
        {periods.map((row) => (
          <div key={row.period} className="px-5 py-4">
            <div className="text-xs font-mono uppercase tracking-widest text-slate-500">{row.period}</div>
            <div className={`mt-2 text-2xl font-semibold ${toneForReturn(row.return)}`}>{pct(row.return)}</div>
            <div className="mt-1 text-xs text-slate-500">
              {price(row.start_price)} to {price(row.end_price)}
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-4">
        <div className="grid grid-cols-[1fr_90px_90px_90px] gap-3 text-xs font-mono uppercase tracking-widest text-slate-500">
          <div>Benchmark</div>
          <div>Period</div>
          <div>Excess</div>
          <div>Result</div>
        </div>
        <div className="mt-2 divide-y divide-border">
          {comparisons.slice(0, 6).map((row) => (
            <div key={`${row.benchmark}-${row.period}`} className="grid grid-cols-[1fr_90px_90px_90px] gap-3 py-2 text-sm">
              <div className="text-ink">{row.benchmark}</div>
              <div className="text-slate-600">{row.period}</div>
              <div className={toneForReturn(row.excess_return)}>{pct(row.excess_return)}</div>
              <div className={row.beat_benchmark ? "text-emerald-700" : "text-rose-700"}>
                {row.beat_benchmark === null ? "n/a" : row.beat_benchmark ? "beat" : "lagged"}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function DecisionOptions({ rows }) {
  return (
    <section className="border border-border bg-panel">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">Decision Options</h2>
      </div>
      <div className="grid grid-cols-1 divide-y divide-border md:grid-cols-4 md:divide-x md:divide-y-0">
        {(rows || []).map((row) => (
          <div key={row.category} className={row.selected ? "bg-slate-50 px-5 py-4" : "px-5 py-4"}>
            <div className={row.selected ? "text-sm font-semibold text-ink" : "text-sm font-semibold text-slate-500"}>
              {row.label}
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">{row.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function AgentDebate({ views }) {
  return (
    <section className="border border-border bg-panel">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">Agent Debate</h2>
      </div>
      <div className="grid grid-cols-1 divide-y divide-border lg:grid-cols-3 lg:divide-x lg:divide-y-0">
        {(views || []).slice(0, 6).map((row, index) => (
          <div key={`${row.perspective}-${row.provider || index}`} className="px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-ink">{row.perspective}</div>
                <div className="mt-1 text-xs font-mono text-slate-500">{row.provider || "no live view"}</div>
              </div>
              <span className="rounded border border-border px-2 py-1 text-xs font-mono text-slate-700">
                {row.action || "n/a"}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700">{row.reasoning}</p>
            {row.headline_used && (
              <p className="mt-3 border-l-2 border-border pl-3 text-xs leading-5 text-slate-500">
                {row.headline_used}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function EvidenceList({ rows }) {
  return (
    <section className="border border-border bg-panel">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">Evidence</h2>
      </div>
      <div className="divide-y divide-border">
        {(rows || []).length === 0 ? (
          <div className="px-5 py-5 text-sm text-slate-500">No local evidence was retrieved for this ticker yet.</div>
        ) : (
          rows.slice(0, 5).map((row) => (
            <div key={row.chunk_id || row.source_url || row.title} className="px-5 py-4">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm font-semibold text-ink">{row.title}</div>
                <div className="text-xs font-mono text-slate-500">
                  {row.ticker || "n/a"} {row.form_type ? `/ ${row.form_type}` : ""}
                </div>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-700">{row.content}</p>
              {row.source_url && (
                <a className="mt-2 inline-block text-xs text-blue-700 hover:underline" href={row.source_url} target="_blank" rel="noreferrer">
                  Source
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function RiskPanel({ risk, triggers, caveats }) {
  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="border border-border bg-panel px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">Risk View</h2>
        <div className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {(risk?.items || []).map((item) => <p key={item}>{item}</p>)}
        </div>
      </div>
      <div className="border border-border bg-panel px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">What Changes The View</h2>
        <div className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {(triggers || []).map((item) => <p key={item}>{item}</p>)}
        </div>
      </div>
      <div className="border border-border bg-panel px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">Caveats</h2>
        <div className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {(caveats || []).map((item) => <p key={item}>{item}</p>)}
        </div>
      </div>
    </section>
  );
}

export default function BriefPage() {
  const [ticker, setTicker] = useState("NVDA");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const result = await getDecisionBrief({ ticker });
        if (!cancelled) {
          setData(result);
          setError(result ? null : "Brief data is unavailable.");
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load brief.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const tickers = useMemo(() => data?.universe?.tradable_tickers || DEFAULT_TICKERS, [data]);

  return (
    <div className="mx-auto max-w-[1320px] space-y-5 px-4 py-6 md:px-8 md:py-8">
      <section className="border border-border bg-panel">
        <div className="grid grid-cols-1 gap-5 px-5 py-5 lg:grid-cols-[1fr_240px] lg:items-start">
          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-slate-500">
              AI Infrastructure Market Recap
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink md:text-3xl">
              {data?.ticker || ticker}
            </h1>
            {loading ? (
              <Skeleton className="mt-4 h-8 max-w-[720px]" />
            ) : (
              <p className="mt-4 max-w-[900px] text-lg leading-8 text-slate-700">
                {data?.so_what || error || "Brief data is unavailable."}
              </p>
            )}
          </div>
          <div>
            <label className="text-xs font-mono uppercase tracking-widest text-slate-500" htmlFor="ticker-select">
              Ticker
            </label>
            <select
              id="ticker-select"
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              className="mt-2 w-full border border-border bg-white px-3 py-2 text-sm text-ink"
            >
              {tickers.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
            {data?.recommendation && (
              <div className={`mt-3 border px-3 py-2 text-sm font-semibold ${categoryTone(data.recommendation.category)}`}>
                {data.recommendation.label} - confidence {Math.round((data.recommendation.confidence || 0) * 100)}%
              </div>
            )}
          </div>
        </div>
      </section>

      {loading ? (
        <Skeleton className="h-[640px]" />
      ) : error ? (
        <div className="border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">{error}</div>
      ) : (
        <>
          <DecisionOptions rows={data?.decision_options} />
          <TrendPanel data={data} />
          <section className="border border-border bg-panel px-5 py-4">
            <h2 className="text-sm font-semibold text-ink">Why It Matters</h2>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              {(data?.why_it_matters || []).map((item) => (
                <div key={item} className="border border-border px-4 py-3 text-sm leading-6 text-slate-700">
                  {item}
                </div>
              ))}
            </div>
          </section>
          <AgentDebate views={data?.agent_debate} />
          <EvidenceList rows={data?.evidence} />
          <RiskPanel
            risk={data?.risk_view}
            triggers={data?.what_would_change_my_mind}
            caveats={data?.caveats}
          />
        </>
      )}
    </div>
  );
}
