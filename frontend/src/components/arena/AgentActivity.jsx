import { useEffect, useMemo, useState } from "react";
import { getAgentActivity } from "../../api/endpoints";
import InfoTooltip from "../ui/InfoTooltip";

const TYPE_STYLES = {
  model: "bg-violet-50 text-violet-700 ring-violet-200",
  tool: "bg-sky-50 text-sky-700 ring-sky-200",
  risk: "bg-amber-50 text-amber-700 ring-amber-200",
  execution: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  decision: "bg-slate-100 text-slate-700 ring-slate-200",
};

const STATUS_STYLES = {
  succeeded: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  filled: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  partial: "bg-amber-50 text-amber-700 ring-amber-200",
  open: "bg-blue-50 text-blue-700 ring-blue-200",
  held: "bg-slate-100 text-slate-600 ring-slate-200",
  empty: "bg-slate-100 text-slate-600 ring-slate-200",
  skipped: "bg-slate-100 text-slate-600 ring-slate-200",
  cached: "bg-blue-50 text-blue-700 ring-blue-200",
  rejected: "bg-rose-50 text-rose-700 ring-rose-200",
  error: "bg-rose-50 text-rose-700 ring-rose-200",
};

const STAGE_LABELS = {
  model_call: "Model",
  rag_retrieval: "RAG",
  mcp_tool_call: "MCP tool",
  risk_check: "Risk",
  order_submit: "Order",
  order_rejected: "Rejected",
  decision: "Decision",
};

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function compactBotName(row) {
  return String(row.bot_name || row.bot_id || "Agent")
    .replace(/\s*\(.*\)/, "")
    .replace("Bot", "")
    .trim();
}

function Pill({ children, className }) {
  return (
    <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-bold ring-1 ${className}`}>
      {children}
    </span>
  );
}

function ActivityRow({ row }) {
  const typeClass = TYPE_STYLES[row.event_type] || TYPE_STYLES.decision;
  const statusClass = STATUS_STYLES[row.status] || STATUS_STYLES.held;
  const stage = STAGE_LABELS[row.stage] || row.stage || "Agent";
  const metadata = row.metadata || {};

  return (
    <li className="border-b border-border py-3 last:border-b-0">
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <Pill className={typeClass}>{stage}</Pill>
          <Pill className={statusClass}>{row.status}</Pill>
          <span className="truncate text-sm font-bold text-ink">{compactBotName(row)}</span>
          {row.llm_provider ? (
            <span className="font-mono text-[11px] uppercase text-slate-500">{row.llm_provider}</span>
          ) : null}
        </div>
        <span className="shrink-0 font-mono text-xs text-slate-400">{formatTime(row.timestamp)}</span>
      </div>
      <p className="mt-2 text-sm leading-5 text-slate-700">{row.summary}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[11px] text-slate-500">
        {row.tool_name ? <span>tool={row.tool_name}</span> : null}
        {row.duration_ms != null ? <span>{Number(row.duration_ms).toFixed(1)}ms</span> : null}
        {metadata.ticker ? <span>{metadata.ticker}</span> : null}
        {row.evidence_ids?.length ? <span>evidence #{row.evidence_ids.join(", #")}</span> : null}
      </div>
    </li>
  );
}

export default function AgentActivity() {
  const [payload, setPayload] = useState(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const data = await getAgentActivity({ eventType: filter, limit: 120 });
      if (cancelled) return;
      if (!data) {
        setError("Unable to load agent activity");
        return;
      }
      setError(null);
      setPayload(data);
    }

    load();
    const timer = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [filter]);

  const rows = payload?.activity || [];
  const counts = useMemo(() => {
    return rows.reduce((acc, row) => {
      acc[row.event_type] = (acc[row.event_type] || 0) + 1;
      return acc;
    }, {});
  }, [rows]);

  return (
    <section className="rounded-xl border border-border bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-sky-700">
            Agent telemetry
            <InfoTooltip label="What is agent telemetry?">
              A public-safe trace of what each agent did: model call, RAG retrieval, MCP-style tool call, risk check,
              and order result. It does not include hidden chain-of-thought, prompts, secrets, or raw tool arguments.
            </InfoTooltip>
          </div>
          <h2 className="mt-1 text-lg font-black tracking-tight text-ink">How decisions move through the system</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Follow the path from context lookup to model proposal, risk gate, and execution outcome.
          </p>
        </div>
        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="min-h-[40px] rounded-lg border border-border bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm outline-none focus:border-claude"
        >
          <option value="">All stages</option>
          <option value="model">Model</option>
          <option value="tool">RAG / MCP tools</option>
          <option value="risk">Risk</option>
          <option value="execution">Execution</option>
          <option value="decision">Holds</option>
        </select>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {["model", "tool", "risk", "execution"].map((key) => (
          <div key={key} className="rounded-lg border border-border bg-slate-50 px-3 py-2">
            <div className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{key}</div>
            <div className="mt-1 font-mono text-lg font-bold text-ink">{counts[key] || 0}</div>
          </div>
        ))}
      </div>

      {error ? (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <ul className="mt-3 max-h-[430px] overflow-y-auto pr-1">
        {!rows.length && !error ? (
          <li className="py-10 text-center font-mono text-sm text-slate-500">
            Waiting for the next agent activity event...
          </li>
        ) : (
          rows.map((row) => <ActivityRow key={row.id} row={row} />)
        )}
      </ul>
    </section>
  );
}
