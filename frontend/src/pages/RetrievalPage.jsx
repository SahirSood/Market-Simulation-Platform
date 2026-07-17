import { useEffect, useState } from "react";
import { getRetrievalSummary } from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function CaseRow({ row }) {
  return (
    <div className="grid grid-cols-[96px_1.4fr_90px_1fr_1fr] gap-3 py-3 border-b border-border last:border-b-0 text-sm">
      <div className={row.hit ? "text-[#22C55E]" : "text-[#EF4444]"}>
        {row.hit ? "hit" : "miss"}
      </div>
      <div>
        <div className="text-[#F1F5F9]">{row.name}</div>
        <div className="text-[#64748B] text-xs font-mono">{row.ticker || "all"}</div>
      </div>
      <div className="text-[#CBD5E1]">{row.hit_rank || "-"}</div>
      <div className="text-[#64748B] truncate">
        {(row.expected_text_contains || []).join(", ") || (row.expected_accession_nos || []).join(", ") || "ids"}
      </div>
      <div className="text-[#64748B] truncate">
        {(row.returned_accession_nos || []).filter(Boolean).join(", ") || (row.returned_chunk_ids || []).join(", ")}
      </div>
    </div>
  );
}

export default function RetrievalPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const data = await getRetrievalSummary();
        if (!cancelled) {
          setSummary(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load retrieval eval");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-[#F1F5F9] font-semibold text-lg">Retrieval Eval</h1>
        <p className="text-[#64748B] text-sm mt-1">
          Labeled RAG cases for checking citation evidence quality and no-lookahead behavior.
        </p>
      </div>

      {error && (
        <div className="bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-5 py-3 text-sm text-[#EF4444]">
          {error}
        </div>
      )}

      {loading ? (
        <Skeleton className="h-[360px] rounded-lg" />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-panel border border-border rounded-lg p-4">
              <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">Recall@K</div>
              <div className="mt-3 text-[#F1F5F9] text-2xl font-semibold">{pct(summary?.recall_at_k)}</div>
            </div>
            <div className="bg-panel border border-border rounded-lg p-4">
              <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">MRR</div>
              <div className="mt-3 text-[#F1F5F9] text-2xl font-semibold">{summary?.mean_reciprocal_rank || 0}</div>
            </div>
            <div className="bg-panel border border-border rounded-lg p-4">
              <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">Hits</div>
              <div className="mt-3 text-[#F1F5F9] text-2xl font-semibold">{summary?.hit_count || 0}/{summary?.case_count || 0}</div>
            </div>
            <div className="bg-panel border border-border rounded-lg p-4">
              <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">Case File</div>
              <div className="mt-3 text-[#F1F5F9] text-sm font-mono truncate">{summary?.case_file}</div>
            </div>
          </div>

          <section className="bg-panel border border-border rounded-lg overflow-x-auto">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-[#F1F5F9]">{summary?.metadata?.name || "Cases"}</h2>
            </div>
            <div className="px-5 min-w-[900px]">
              <div className="grid grid-cols-[96px_1.4fr_90px_1fr_1fr] gap-3 py-3 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
                <div>Status</div>
                <div>Case</div>
                <div>Rank</div>
                <div>Expected</div>
                <div>Returned</div>
              </div>
              {(summary?.cases || []).map((row) => (
                <CaseRow key={row.name} row={row} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
