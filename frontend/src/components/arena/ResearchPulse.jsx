import { useEffect, useMemo, useState } from "react";
import { getEvaluationSummary, getIngestionStatus, getRagStatus } from "../../api/endpoints";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function Field({ label, value, tone = "default" }) {
  const color = tone === "good" ? "text-[#22C55E]" : tone === "warn" ? "text-[#F97316]" : "text-[#CBD5E1]";
  return (
    <div className="min-w-0 rounded-lg border border-border bg-bg px-4 py-3">
      <div className="text-[10px] font-mono uppercase tracking-widest text-[#64748B]">{label}</div>
      <div className={`mt-1 truncate font-mono text-sm font-semibold ${color}`}>{value ?? "n/a"}</div>
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
    ingestion: null,
    evaluation: null,
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [rag, ingestion, evaluation] = await Promise.all([
        getRagStatus(),
        getIngestionStatus(),
        getEvaluationSummary(),
      ]);
      if (!cancelled) setData({ rag, ingestion, evaluation });
    }

    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const coverage = useMemo(() => {
    const docs = Number(data.rag?.document_count || 0);
    const chunks = Number(data.rag?.chunk_count || 0);
    const pending = data.rag?.pending_embedding_count_sample;
    return {
      docs,
      chunks,
      pending,
      embedded: pending === 0,
    };
  }, [data.rag]);

  const totals = data.evaluation?.totals || {};
  const ingestionJobs = data.ingestion?.recent_ingestion_jobs || [];
  const embeddingJobs = data.rag?.recent_embedding_jobs || [];
  const research = data.ingestion?.research || {};
  const scheduler = data.ingestion?.scheduler || {};
  const providerBudgets = scheduler.provider_budgets || {};
  const claudeBudget = providerBudgets.claude || {};
  const openaiBudget = providerBudgets.openai || {};

  return (
    <section className="rounded-xl border border-border bg-panel p-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[#F1F5F9]">Research Pulse</h2>
          <p className="mt-1 text-xs text-[#64748B]">SEC evidence, ingestion jobs, citations, and unsupported trade checks.</p>
        </div>
        <div className="font-mono text-xs text-[#64748B]">
          {data.ingestion?.news_api_configured ? "News live" : "News offline"} / {data.rag?.embedding_service_configured ? "Embeddings live" : "Embeddings offline"}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="SEC Docs" value={coverage.docs} tone={coverage.docs > 0 ? "good" : "warn"} />
        <Field label="Chunks" value={coverage.chunks} tone={coverage.chunks > 0 ? "good" : "warn"} />
        <Field label="Pending Embeds" value={coverage.pending ?? "n/a"} tone={coverage.embedded ? "good" : "warn"} />
        <Field label="Citation Rate" value={pct(totals.citation_rate)} tone={totals.citation_rate > 0 ? "good" : "warn"} />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Field label="Ingestion Job" value={latestJobLabel(ingestionJobs)} tone={latestJobLabel(ingestionJobs).startsWith("succeeded") ? "good" : "warn"} />
        <Field label="Embedding Job" value={latestJobLabel(embeddingJobs)} tone={latestJobLabel(embeddingJobs).startsWith("succeeded") ? "good" : "warn"} />
        <Field label="Ingested Tickers" value={tickersFromJob(ingestionJobs)} />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Field label="Auto Research" value={research.enabled ? "on" : "off"} tone={research.enabled ? "good" : "warn"} />
        <Field label="Research Queue" value={`${research.queued_count || 0} queued / ${research.processed_today || 0} today`} />
        <Field label="Market Gate" value={scheduler.market_hours_only ? (scheduler.market_open ? "market open" : "market closed") : "always on"} tone={scheduler.market_hours_only && !scheduler.market_open ? "warn" : "good"} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field
          label="Daily LLM Calls"
          value={budgetText(scheduler.daily_billable_calls, scheduler.daily_decision_budget, "today")}
          tone={budgetTone(scheduler.daily_billable_calls, scheduler.daily_decision_budget)}
        />
        <Field
          label="Monthly Calls"
          value={budgetText(scheduler.monthly_billable_calls, scheduler.monthly_decision_budget, "month")}
          tone={budgetTone(scheduler.monthly_billable_calls, scheduler.monthly_decision_budget)}
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
    </section>
  );
}
