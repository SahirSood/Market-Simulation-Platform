import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getRagCatalog,
  getRagDocument,
  getRagDocuments,
  getRetrievalHistory,
  getRetrievalSummary,
} from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";
import { downloadCsv, downloadJson, flattenForCsv } from "../lib/exportUtils";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function number(value) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function compact(value) {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "n/a";
  return new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function sourceLabel(value) {
  return String(value || "document").replace(/_/g, " ");
}

function optionRows(rows, emptyLabel) {
  return [{ value: "", label: emptyLabel }, ...(rows || []).map((row) => ({
    value: row.value,
    label: `${row.value} (${row.count})`,
  }))];
}

function Metric({ label, value, sub, tone = "default" }) {
  const toneClass =
    tone === "good"
      ? "bg-emerald-50 text-emerald-700"
      : tone === "warn"
        ? "bg-amber-50 text-amber-700"
        : "bg-white text-ink";
  return (
    <div className={`min-w-0 rounded-2xl border border-border ${toneClass} p-4 shadow-sm`}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className="mt-2 break-words font-mono text-xl font-black leading-tight">{value}</div>
      {sub ? <div className="mt-1 break-words text-xs text-slate-500">{sub}</div> : null}
    </div>
  );
}

function ExportButton({ children, onClick, disabled = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "rounded-full border border-border px-3 py-2 text-xs font-semibold transition-colors",
        disabled
          ? "cursor-not-allowed text-slate-400"
          : "bg-white text-slate-700 shadow-sm hover:bg-slate-100",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="grid gap-1 text-xs font-semibold text-slate-500">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[42px] rounded-full border border-border bg-white px-4 text-sm font-medium text-slate-700 shadow-sm outline-none focus:border-claude"
      >
        {options.map((option) => (
          <option key={option.value || option.label} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Pill({ children, tone = "default" }) {
  const cls =
    tone === "blue"
      ? "bg-blue-50 text-blue-700"
      : tone === "orange"
        ? "bg-orange-50 text-orange-700"
        : tone === "green"
          ? "bg-emerald-50 text-emerald-700"
          : "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${cls}`}>
      {children}
    </span>
  );
}

function categoryTone(category) {
  if (String(category).toLowerCase().includes("sec")) return "blue";
  if (String(category).toLowerCase().includes("earnings")) return "orange";
  return "default";
}

function DocumentRow({ doc, selected, onSelect }) {
  const embedded = Number(doc.pending_embedding_count || 0) === 0;
  return (
    <button
      type="button"
      onClick={() => onSelect(doc.id)}
      className={[
        "w-full rounded-2xl border p-4 text-left transition-all",
        selected ? "border-claude bg-blue-50/70 shadow-sm" : "border-border bg-white hover:border-slate-300 hover:bg-slate-50",
      ].join(" ")}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={doc.ticker ? "green" : "default"}>{doc.ticker || "Market"}</Pill>
        <Pill tone={categoryTone(doc.category)}>{doc.category || sourceLabel(doc.source_type)}</Pill>
        {doc.form_type ? <Pill>{doc.form_type}</Pill> : null}
        {doc.citation_count > 0 ? <Pill tone="orange">{doc.citation_count} cites</Pill> : null}
      </div>
      <div className="mt-3 flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-black text-ink">{doc.title || "Untitled document"}</h3>
          <p className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600">{doc.ingestion_reason}</p>
        </div>
        <div className="shrink-0 font-mono text-xs text-slate-500 sm:text-right">
          <div>{formatDate(doc.published_at || doc.created_at)}</div>
          <div>{number(doc.chunk_count)} chunks</div>
        </div>
      </div>
      <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
        <span className="truncate">{doc.source_name || sourceLabel(doc.source_type)}</span>
        <span className={embedded ? "text-emerald-700" : "text-amber-700"}>
          {embedded ? "embedded" : `${doc.pending_embedding_count} pending embeds`}
        </span>
        <span className="truncate">{doc.accession_no || `${compact(doc.content_length)} chars`}</span>
      </div>
    </button>
  );
}

function DocumentDetail({ doc, loading }) {
  if (loading) {
    return <Skeleton className="h-[520px] rounded-3xl" />;
  }
  if (!doc) {
    return (
      <section className="rounded-3xl border border-border bg-white p-5 text-sm text-slate-500 shadow-sm">
        No document selected.
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={doc.ticker ? "green" : "default"}>{doc.ticker || "Market"}</Pill>
        <Pill tone={categoryTone(doc.category)}>{doc.category}</Pill>
        {doc.form_type ? <Pill>{doc.form_type}</Pill> : null}
      </div>
      <h2 className="mt-4 text-lg font-black tracking-tight text-ink">{doc.title || "Untitled document"}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">{doc.ingestion_reason}</p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Metric label="Chunks" value={number(doc.chunk_count)} sub={`${number(doc.pending_embedding_count)} pending`} tone={doc.pending_embedding_count ? "warn" : "good"} />
        <Metric label="Citations" value={number(doc.citation_count)} sub="bot evidence refs" tone={doc.citation_count ? "good" : "default"} />
        <Metric label="Published" value={formatDate(doc.published_at)} sub={doc.accession_no} />
        <Metric label="Size" value={compact(doc.content_length)} sub="stored characters" />
      </div>

      <div className="mt-4 grid gap-2 text-xs text-slate-500">
        {doc.source_url ? (
          <a className="truncate font-semibold text-claude hover:underline" href={doc.source_url} target="_blank" rel="noreferrer">
            {doc.source_url}
          </a>
        ) : null}
        {doc.cik ? <div className="font-mono">CIK {doc.cik}</div> : null}
      </div>

      <div className="mt-5">
        <h3 className="text-[11px] font-mono uppercase tracking-widest text-slate-500">Stored Excerpts</h3>
        <div className="mt-3 grid gap-3">
          {(doc.chunks || []).map((chunk) => (
            <article key={chunk.chunk_id} className="rounded-2xl border border-border bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs font-bold text-slate-600">chunk {chunk.chunk_id}</span>
                <span className={chunk.has_embedding ? "text-xs font-semibold text-emerald-700" : "text-xs font-semibold text-amber-700"}>
                  {chunk.has_embedding ? "embedded" : "pending embedding"}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-700">{chunk.content}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function HistoryChart({ history }) {
  const rows = [...history].reverse().map((row, index) => ({
    run: index + 1,
    recall: Math.round((row.recall_at_k || 0) * 100),
    mrr: Number(row.mean_reciprocal_rank || 0),
  }));
  if (rows.length === 0) return null;
  return (
    <section className="rounded-3xl border border-border bg-white p-5 shadow-sm">
      <h2 className="text-sm font-black text-ink">Retrieval Trend</h2>
      <div className="mt-4 h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
            <XAxis dataKey="run" stroke="#94A3B8" tickLine={false} />
            <YAxis stroke="#94A3B8" tickLine={false} yAxisId="left" tickFormatter={(value) => `${value}%`} />
            <YAxis stroke="#94A3B8" tickLine={false} yAxisId="right" orientation="right" domain={[0, 1]} />
            <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }} />
            <Line yAxisId="left" dataKey="recall" stroke="#16A34A" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="right" dataKey="mrr" stroke="#2563EB" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function CaseRow({ row }) {
  return (
    <div className="grid grid-cols-[80px_1.3fr_80px_1fr_1fr] gap-3 border-b border-border py-3 text-sm last:border-b-0">
      <div className={row.hit ? "font-semibold text-emerald-600" : "font-semibold text-rose-600"}>
        {row.hit ? "hit" : "miss"}
      </div>
      <div>
        <div className="font-semibold text-ink">{row.name}</div>
        <div className="font-mono text-xs text-slate-500">{row.ticker || "all"}</div>
      </div>
      <div className="text-slate-700">{row.hit_rank || "-"}</div>
      <div className="truncate text-slate-500">
        {(row.expected_text_contains || []).join(", ") || (row.expected_accession_nos || []).join(", ") || "ids"}
      </div>
      <div className="truncate text-slate-500">
        {(row.returned_accession_nos || []).filter(Boolean).join(", ") || (row.returned_chunk_ids || []).join(", ")}
      </div>
    </div>
  );
}

export default function RetrievalPage() {
  const [catalog, setCatalog] = useState(null);
  const [documents, setDocuments] = useState({ documents: [], total: 0, limit: 50, offset: 0 });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [filters, setFilters] = useState({ ticker: "", sourceType: "", formType: "", q: "" });
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const [catalogData, summaryData, historyData] = await Promise.all([
          getRagCatalog(),
          getRetrievalSummary(),
          getRetrievalHistory(12),
        ]);
        if (!catalogData) throw new Error("Failed to load RAG catalog");
        if (!cancelled) {
          setCatalog(catalogData);
          setSummary(summaryData);
          setHistory(historyData?.history || []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load RAG data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadDocs() {
      try {
        setDocsLoading(true);
        const data = await getRagDocuments(filters);
        if (!data) throw new Error("Failed to load ingested documents");
        if (!cancelled) {
          setDocuments(data);
          const rows = data.documents || [];
          if (rows.length && !rows.some((doc) => doc.id === selectedId)) {
            setSelectedId(rows[0].id);
          }
          if (!rows.length) {
            setSelectedId(null);
            setSelectedDoc(null);
          }
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load ingested documents");
      } finally {
        if (!cancelled) setDocsLoading(false);
      }
    }
    loadDocs();
    return () => {
      cancelled = true;
    };
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    async function loadDetail() {
      if (!selectedId) return;
      try {
        setDetailLoading(true);
        const data = await getRagDocument(selectedId, 10);
        if (!cancelled) setSelectedDoc(data);
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const cases = summary?.cases || [];
  const docsRows = useMemo(() => (documents.documents || []).map((row) => flattenForCsv(row)), [documents]);
  const casesRows = useMemo(() => cases.map((row) => flattenForCsv(row)), [cases]);
  const historyRows = useMemo(() => history.map((row) => flattenForCsv(row)), [history]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetFilters = () => setFilters({ ticker: "", sourceType: "", formType: "", q: "" });

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 px-6 py-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
            Research library
          </div>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-ink">RAG evidence the bots can cite</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Ingested filings, bot-triggered research, embeddings, citations, and retrieval checks.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ExportButton disabled={loading || !catalog} onClick={() => downloadJson("rag-catalog", catalog)}>
            Catalog JSON
          </ExportButton>
          <ExportButton disabled={docsRows.length === 0} onClick={() => downloadCsv("rag-documents", docsRows)}>
            Documents CSV
          </ExportButton>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-600">
          {error}
        </div>
      )}

      {loading ? (
        <Skeleton className="h-[300px] rounded-3xl" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Metric label="Documents" value={number(catalog?.document_count)} tone={catalog?.document_count ? "good" : "warn"} />
            <Metric label="Chunks" value={number(catalog?.chunk_count)} tone={catalog?.chunk_count ? "good" : "warn"} />
            <Metric label="Embeddings" value={catalog?.pending_embedding_count ? "pending" : "ready"} sub={`${number(catalog?.pending_embedding_count)} pending`} tone={catalog?.pending_embedding_count ? "warn" : "good"} />
            <Metric label="Tickers" value={number(catalog?.tickers?.length)} sub={(catalog?.tickers || []).slice(0, 3).map((row) => row.value).join(", ")} />
            <Metric label="Recall@K" value={pct(summary?.recall_at_k)} sub={`${summary?.hit_count || 0}/${summary?.case_count || 0} eval hits`} tone={summary?.recall_at_k ? "good" : "warn"} />
          </div>

          <section className="rounded-3xl border border-border bg-white p-5 shadow-sm">
            <div className="grid gap-3 lg:grid-cols-[1.2fr_180px_220px_180px_auto] lg:items-end">
              <label className="grid gap-1 text-xs font-semibold text-slate-500">
                Search
                <input
                  value={filters.q}
                  onChange={(event) => updateFilter("q", event.target.value)}
                  placeholder="ticker, accession, filing text"
                  className="min-h-[42px] rounded-full border border-border bg-white px-4 text-sm text-slate-700 shadow-sm outline-none focus:border-claude"
                />
              </label>
              <FilterSelect
                label="Ticker"
                value={filters.ticker}
                onChange={(value) => updateFilter("ticker", value)}
                options={optionRows(catalog?.tickers, "All tickers")}
              />
              <FilterSelect
                label="Source"
                value={filters.sourceType}
                onChange={(value) => updateFilter("sourceType", value)}
                options={optionRows(catalog?.source_types, "All sources")}
              />
              <FilterSelect
                label="Form"
                value={filters.formType}
                onChange={(value) => updateFilter("formType", value)}
                options={optionRows(catalog?.form_types, "All forms")}
              />
              <button
                type="button"
                onClick={resetFilters}
                className="min-h-[42px] rounded-full border border-border bg-slate-50 px-4 text-sm font-semibold text-slate-600 hover:bg-slate-100"
              >
                Reset
              </button>
            </div>
          </section>

          <div className="grid gap-5 xl:grid-cols-[1fr_420px] xl:items-start">
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-black text-ink">{number(documents.total)} ingested documents</h2>
                <span className="font-mono text-xs text-slate-500">{docsLoading ? "loading" : "live"}</span>
              </div>
              {docsLoading ? (
                <Skeleton className="h-[420px] rounded-3xl" />
              ) : documents.documents?.length ? (
                documents.documents.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    doc={doc}
                    selected={selectedId === doc.id}
                    onSelect={setSelectedId}
                  />
                ))
              ) : (
                <div className="rounded-3xl border border-border bg-white p-8 text-sm text-slate-500 shadow-sm">
                  No documents match the current filters.
                </div>
              )}
            </section>

            <DocumentDetail doc={selectedDoc} loading={detailLoading} />
          </div>

          <section className="rounded-3xl border border-border bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="text-xs font-bold uppercase tracking-wide text-slate-500">Retrieval quality</div>
                <h2 className="mt-1 text-lg font-black text-ink">{summary?.metadata?.name || "RAG benchmark"}</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <ExportButton disabled={!summary} onClick={() => downloadJson("retrieval-summary", summary)}>
                  Eval JSON
                </ExportButton>
                <ExportButton disabled={casesRows.length === 0} onClick={() => downloadCsv("retrieval-cases", casesRows)}>
                  Cases CSV
                </ExportButton>
                <ExportButton disabled={historyRows.length === 0} onClick={() => downloadCsv("retrieval-history", historyRows)}>
                  History CSV
                </ExportButton>
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-4">
              <Metric label="Recall@K" value={pct(summary?.recall_at_k)} />
              <Metric label="MRR" value={summary?.mean_reciprocal_rank || 0} />
              <Metric label="Hits" value={`${summary?.hit_count || 0}/${summary?.case_count || 0}`} />
              <Metric label="Case File" value={summary?.case_file || "n/a"} sub="current eval suite" />
            </div>
          </section>

          <HistoryChart history={history} />

          <section className="overflow-x-auto rounded-3xl border border-border bg-white shadow-sm">
            <div className="min-w-[860px] px-5">
              <div className="grid grid-cols-[80px_1.3fr_80px_1fr_1fr] gap-3 border-b border-border py-3 text-xs font-mono uppercase tracking-widest text-slate-500">
                <div>Status</div>
                <div>Case</div>
                <div>Rank</div>
                <div>Expected</div>
                <div>Returned</div>
              </div>
              {cases.length === 0 ? (
                <div className="py-5 text-sm text-slate-500">No retrieval cases returned.</div>
              ) : (
                cases.map((row) => <CaseRow key={row.name} row={row} />)
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
