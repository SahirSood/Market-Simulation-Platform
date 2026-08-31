import { useEffect, useState } from "react";
import { getIngestionStatus, getModelConfig, getRagStatus, getRiskLimits } from "../api/endpoints";
import InfoTooltip from "../components/ui/InfoTooltip";
import Skeleton from "../components/ui/Skeleton";

function Field({ label, value }) {
  return (
    <div className="border-b border-border last:border-b-0 py-3">
      <div className="text-slate-500 text-xs font-mono uppercase tracking-widest">{humanLabel(label)}</div>
      <div className="mt-1 text-slate-700 text-sm break-words">{String(value ?? "n/a")}</div>
    </div>
  );
}

function BotRow({ row }) {
  return (
    <div className="grid grid-cols-[1.2fr_120px_1fr_120px] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div>
        <div className="text-ink">{row.bot_name}</div>
        <div className="text-slate-500 text-xs font-mono">{row.bot_id}</div>
      </div>
      <div className="text-slate-700 capitalize">{row.provider}</div>
      <div className="text-slate-700 font-mono truncate">{row.model}</div>
      <div className="text-slate-500 font-mono truncate">{row.prompt_version}</div>
    </div>
  );
}

function joinList(values) {
  return Array.isArray(values) ? values.join(", ") : values;
}

function humanLabel(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function ConfigPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const [models, risk, rag, ingestion] = await Promise.all([
          getModelConfig(),
          getRiskLimits(),
          getRagStatus(),
          getIngestionStatus(),
        ]);
        if (!cancelled) {
          setData({ models, risk, rag, ingestion });
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load config");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const limits = data?.risk?.risk_limits || {};

  return (
    <div className="mx-auto max-w-[1280px] space-y-5 px-4 py-6 md:px-8 md:py-8">
      <div>
        <div className="flex items-center gap-1">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Configuration</h1>
          <InfoTooltip label="Why setup is public">
            This page exposes safe configuration: model names, public mode, risk limits, data status, and cost controls.
            It does not expose API keys, secrets, prompts, or operator-only controls.
          </InfoTooltip>
        </div>
        <p className="text-slate-500 text-sm mt-1">
          Public model matchup, risk limits, data freshness, and cost guardrails.
        </p>
      </div>

      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-lg px-5 py-3 text-sm text-rose-600">
          {error}
        </div>
      )}

      {loading ? (
        <Skeleton className="h-[420px] rounded-lg" />
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-ink mb-2">Model Matchup</h2>
              <Field label="Prompt Version" value={data?.models?.prompt_version} />
              <Field
                label="Claude"
                value={`${data?.models?.providers?.claude?.model || "n/a"} · ${data?.models?.providers?.claude?.effort || "default"} effort · ${data?.models?.providers?.claude?.configured ? "configured" : "missing key"}`}
              />
              <Field
                label="OpenAI"
                value={`${data?.models?.providers?.openai?.model || "n/a"} · ${data?.models?.providers?.openai?.reasoning_effort || "default"} effort · ${data?.models?.providers?.openai?.configured ? "configured" : "missing key"}`}
              />
              <Field label="Starting Cash" value={data?.models?.starting_cash} />
              <Field label="Public Mode" value={data?.models?.public_read_only ? "view only" : "operator"} />
            </section>
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-ink mb-2">Risk Limits</h2>
              {Object.entries(limits).map(([key, value]) => (
                <Field key={key} label={key} value={value} />
              ))}
            </section>
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-ink mb-2">Evidence & Data</h2>
              <Field label="RAG Configured" value={data?.rag?.configured} />
              <Field label="Documents" value={data?.rag?.document_count} />
              <Field label="Chunks" value={data?.rag?.chunk_count} />
              <Field label="Pending Embeddings" value={data?.rag?.pending_embedding_count_sample} />
              <Field label="Live News" value={data?.ingestion?.live_data?.news_available ?? data?.ingestion?.news_api_configured} />
              <Field label="SEC Evidence" value={data?.ingestion?.live_data?.sec_filings_available ?? data?.ingestion?.sec_user_agent_configured} />
              <Field label="Market Open" value={data?.ingestion?.scheduler?.market_open} />
              <Field label="Cost Guard" value={data?.ingestion?.scheduler?.cost_guard_enabled} />
            </section>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-ink mb-2">Trading</h2>
              <Field label="Tradable Tickers" value={joinList(data?.models?.trading?.tradable_tickers)} />
              <Field label="Benchmark Tickers" value={joinList(data?.models?.trading?.benchmark_tickers)} />
              <Field label="Short Selling" value={data?.models?.trading?.short_selling_enabled ? "enabled with position limits" : "disabled"} />
              <Field label="Execution" value="C++ limit order book with seeded demo liquidity" />
              <Field label="Access" value={data?.models?.public_read_only ? "public dashboard is read only" : "operator mode"} />
            </section>
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-ink mb-2">Cost Controls</h2>
              <Field label="Monthly Spend Limit" value={data?.models?.cost_controls?.llm_monthly_spend_limit_usd} />
              <Field label="Daily Spend Limit" value={data?.models?.cost_controls?.llm_daily_spend_limit_usd} />
              <Field label="Monthly Spend Used" value={data?.ingestion?.scheduler?.monthly_estimated_llm_cost_usd} />
              <Field label="Daily Spend Used" value={data?.ingestion?.scheduler?.daily_estimated_llm_cost_usd} />
              <Field label="Budget Exhausted" value={data?.ingestion?.scheduler?.spend_budget_exhausted} />
            </section>
          </div>

          <details className="rounded-lg border border-border bg-panel">
            <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold text-ink">
              Live bot metadata
            </summary>
            <div className="overflow-x-auto border-t border-border px-5">
              <div className="min-w-[900px]">
                <div className="grid grid-cols-[1.2fr_120px_1fr_120px] gap-3 py-3 text-xs font-mono uppercase tracking-widest text-slate-500 border-b border-border">
                  <div>Bot</div>
                  <div>Provider</div>
                  <div>Model</div>
                  <div>Prompt</div>
                </div>
                {(data?.models?.live_bots || []).map((row) => (
                  <BotRow key={row.bot_id} row={row} />
                ))}
              </div>
            </div>
          </details>
        </>
      )}
    </div>
  );
}
