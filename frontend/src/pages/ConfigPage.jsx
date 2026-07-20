import { useEffect, useState } from "react";
import { getIngestionStatus, getModelConfig, getRagStatus, getRiskLimits } from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";

function Field({ label, value }) {
  return (
    <div className="border-b border-border last:border-b-0 py-3">
      <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">{label}</div>
      <div className="mt-1 text-[#CBD5E1] text-sm break-words">{String(value ?? "n/a")}</div>
    </div>
  );
}

function BotRow({ row }) {
  return (
    <div className="grid grid-cols-[1.2fr_100px_1fr_90px_1fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div>
        <div className="text-[#F1F5F9]">{row.bot_name}</div>
        <div className="text-[#64748B] text-xs font-mono">{row.bot_id}</div>
      </div>
      <div className="text-[#CBD5E1] capitalize">{row.provider}</div>
      <div className="text-[#CBD5E1] font-mono truncate">{row.model}</div>
      <div className={row.tool_mode_enabled ? "text-[#22C55E]" : "text-[#64748B]"}>
        {row.tool_mode_enabled ? "on" : "off"}
      </div>
      <div className="text-[#64748B] font-mono truncate">{row.prompt_hash}</div>
    </div>
  );
}

function latestStatus(rows) {
  const row = (rows || [])[0];
  if (!row) return "none";
  return `${row.status} (${row.attempts}/${row.max_attempts})`;
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
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-[#F1F5F9] font-semibold text-lg">Config</h1>
        <p className="text-[#64748B] text-sm mt-1">
          Model versions, prompt hashes, risk limits, and local ops status.
        </p>
      </div>

      {error && (
        <div className="bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-5 py-3 text-sm text-[#EF4444]">
          {error}
        </div>
      )}

      {loading ? (
        <Skeleton className="h-[420px] rounded-lg" />
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-[#F1F5F9] mb-2">Models</h2>
              <Field label="Prompt Version" value={data?.models?.prompt_version} />
              <Field label="Claude" value={data?.models?.providers?.claude?.model} />
              <Field label="OpenAI" value={data?.models?.providers?.openai?.model} />
              <Field label="Starting Cash" value={data?.models?.starting_cash} />
              <Field label="Embedding" value={data?.models?.rag?.embedding_model} />
            </section>
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-[#F1F5F9] mb-2">Risk Limits</h2>
              {Object.entries(limits).map(([key, value]) => (
                <Field key={key} label={key} value={value} />
              ))}
            </section>
            <section className="bg-panel border border-border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-[#F1F5F9] mb-2">Ops</h2>
              <Field label="RAG Configured" value={data?.rag?.configured} />
              <Field label="Documents" value={data?.rag?.document_count} />
              <Field label="Chunks" value={data?.rag?.chunk_count} />
              <Field label="Embedding Job" value={latestStatus(data?.rag?.recent_embedding_jobs)} />
              <Field label="SEC User Agent" value={data?.ingestion?.sec_user_agent_configured} />
              <Field label="Ingestion Job" value={latestStatus(data?.ingestion?.recent_ingestion_jobs)} />
              <Field label="Write Auth" value={data?.ingestion?.write_auth_configured} />
              <Field label="Audit Log" value={data?.ingestion?.audit_log_configured} />
              <Field label="HTTP MCP" value={data?.ingestion?.mcp_http_configured} />
              <Field label="Job Backend" value={data?.ingestion?.job_backend} />
            </section>
          </div>

          <section className="bg-panel border border-border rounded-lg overflow-x-auto">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-[#F1F5F9]">Live Bot Metadata</h2>
            </div>
            <div className="px-5 min-w-[900px]">
              <div className="grid grid-cols-[1.2fr_100px_1fr_90px_1fr] gap-3 py-3 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
                <div>Bot</div>
                <div>Provider</div>
                <div>Model</div>
                <div>Tools</div>
                <div>Prompt Hash</div>
              </div>
              {(data?.models?.live_bots || []).map((row) => (
                <BotRow key={row.bot_id} row={row} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
