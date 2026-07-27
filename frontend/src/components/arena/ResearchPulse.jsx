import { useEffect, useMemo, useState } from "react";
import { getEvaluationSummary, getIngestionStatus, getRagCatalog, getRagStatus } from "../../api/endpoints";
import InfoTooltip from "../ui/InfoTooltip";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function Field({ label, value, tone = "default" }) {
  const color =
    tone === "good"
      ? "text-emerald-700"
      : tone === "warn"
        ? "text-amber-700"
        : "text-slate-800";
  const bg =
    tone === "good"
      ? "bg-emerald-50"
      : tone === "warn"
        ? "bg-amber-50"
        : "bg-slate-50";
  return (
    <div className={`min-w-0 rounded-md border border-border ${bg} px-4 py-3`}>
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className={`mt-1 truncate text-sm font-semibold tabular-nums ${color}`}>{value ?? "n/a"}</div>
    </div>
  );
}

function latestJobLabel(jobs) {
  const job = Array.isArray(jobs) ? jobs[0] : null;
  if (!job) return "none";
  return `${job.status} (${job.attempts}/${job.max_attempts})`;
}

function tickersFromJob(jobs) {
  const job = Array.isArray(jobs) ? jobs[0] : null;
  const tickers = job?.metadata?.updated_tickers || job?.metadata?.tickers || [];
  return Array.isArray(tickers) && tickers.length ? tickers.join(", ") : "none";
}

function budgetText(used, limit, period) {
  const count = Number(used || 0);
  const cap = Number(limit || 0);
  return cap > 0 ? `${count}/${cap} ${period}` : `${count}/unlimited ${period}`;
}

function budgetTone(used, limit) {
  const count = Number(used || 0);
  const cap = Number(limit || 0);
  if (cap <= 0) return "good";
  return count / cap >= 0.8 ? "warn" : "good";
}

export default function ResearchPulse() {
  const [data, setData] = useState({
    rag: null,
    catalog: null,
    ingestion: null,
    evaluation: null,
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [rag, catalog, ingestion, evaluation] = await Promise.all([
        getRagStatus(),
        getRagCatalog(),
        getIngestionStatus(),
        getEvaluationSummary(),
      ]);
      if (!cancelled) setData({ rag, catalog, ingestion, evaluation });
    }

    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const coverage = useMemo(() => {
    const counts = data.catalog || data.rag;
    const docs = Number(counts?.document_count || 0);
    const chunks = Number(counts?.chunk_count || 0);
    const pending = data.catalog
      ? data.catalog.pending_embedding_count
      : data.rag?.pending_embedding_count_sample;
    return {
      docs,
      chunks,
      pending,
      embedded: pending === 0,
      tickers: Number(data.catalog?.tickers?.length || 0),
      duplicates:
        data.catalog?.duplicate_document_count == null
          ? null
          : Number(data.catalog.duplicate_document_count),
    };
  }, [data.catalog, data.rag]);

  const totals = data.evaluation?.totals || {};
  const ingestionJobs = data.ingestion?.recent_ingestion_jobs || [];
  const embeddingJobs = data.catalog?.recent_embedding_jobs || data.rag?.recent_embedding_jobs || [];
  const research = data.ingestion?.research || {};
  const scheduler = data.ingestion?.scheduler || {};
  const providerBudgets = scheduler.provider_budgets || {};
  const claudeBudget = providerBudgets.claude || {};
  const openaiBudget = providerBudgets.openai || {};
  const marketGate = scheduler.market_hours_only
    ? scheduler.market_open
      ? "market open"
      : "market closed"
    : "always on";

  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
            Research and controls
            <InfoTooltip label="What is the research layer?">
              RAG is the evidence system. It stores filing chunks, embeds them, retrieves relevant sources, and exposes
              citations so the agents are not trading from vibes alone.
            </InfoTooltip>
          </div>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink">Evidence and cost guardrails</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            The agents use a small live SEC evidence library, short prompts, and strict spend limits.
          </p>
        </div>
        <div className="rounded-md bg-slate-100 px-3 py-1.5 text-xs text-slate-600">
          {data.ingestion?.news_api_configured ? "News live" : "News offline"} /{" "}
          {data.rag?.embedding_service_configured ? "Embeddings live" : "Embeddings offline"}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Field label="Unique SEC filings" value={coverage.docs} tone={coverage.docs > 0 ? "good" : "warn"} />
        <Field label="Chunks" value={coverage.chunks} tone={coverage.chunks > 0 ? "good" : "warn"} />
        <Field label="Embeddings" value={coverage.embedded ? "ready" : `${coverage.pending ?? "n/a"} pending`} tone={coverage.embedded ? "good" : "warn"} />
        <Field label="Covered tickers" value={coverage.tickers} tone={coverage.tickers > 0 ? "good" : "warn"} />
        <Field
          label="Duplicate records"
          value={coverage.duplicates ?? "not checked"}
          tone={coverage.duplicates == null ? "default" : coverage.duplicates === 0 ? "good" : "warn"}
        />
        <Field label="Market Gate" value={marketGate} tone={scheduler.market_hours_only && !scheduler.market_open ? "warn" : "good"} />
      </div>

      <p className="mt-3 text-xs leading-5 text-slate-500">
        These counts use the same live catalog as the Research page. Repeated tickers can represent separate SEC
        filings; duplicate detection uses accession number, source URL, and exact content identity.
      </p>

      <details className="mt-3 rounded-lg border border-border bg-slate-50 px-3 py-2">
        <summary className="cursor-pointer list-none text-sm font-bold text-slate-800">
          Details: ingestion, citations, and LLM budgets
        </summary>
        <div className="mt-3 grid gap-3">
          <Field
            label="Latest Ingestion"
            value={`${latestJobLabel(ingestionJobs)} / ${tickersFromJob(ingestionJobs)}`}
            tone={latestJobLabel(ingestionJobs).startsWith("succeeded") ? "good" : "warn"}
          />
          <Field
            label="Latest Embedding"
            value={latestJobLabel(embeddingJobs)}
            tone={latestJobLabel(embeddingJobs).startsWith("succeeded") ? "good" : "warn"}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Citation Rate" value={pct(totals.citation_rate)} tone={totals.citation_rate > 0 ? "good" : "warn"} />
            <Field label="Auto Research" value={research.enabled ? "on" : "off"} tone={research.enabled ? "good" : "warn"} />
            <Field label="Queue" value={`${research.queued_count || 0} queued / ${research.processed_today || 0} today`} />
            <Field
              label="Daily LLM Calls"
              value={budgetText(scheduler.daily_billable_calls, scheduler.daily_decision_budget, "today")}
              tone={budgetTone(scheduler.daily_billable_calls, scheduler.daily_decision_budget)}
            />
            <Field
              label="Claude Calls"
              value={budgetText(claudeBudget.daily_billable_calls, claudeBudget.daily_limit, "today")}
              tone={budgetTone(claudeBudget.daily_billable_calls, claudeBudget.daily_limit)}
            />
            <Field
              label="OpenAI Calls"
              value={budgetText(openaiBudget.daily_billable_calls, openaiBudget.daily_limit, "today")}
              tone={budgetTone(openaiBudget.daily_billable_calls, openaiBudget.daily_limit)}
            />
          </div>
        </div>
      </details>
    </section>
  );
}
