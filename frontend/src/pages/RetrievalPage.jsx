import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getRetrievalHistory, getRetrievalSummary } from "../api/endpoints";
import Skeleton from "../components/ui/Skeleton";
import { downloadCsv, downloadJson, flattenForCsv } from "../lib/exportUtils";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function Metric({ label, value, sub, compact = false }) {
  return (
    <div className="bg-panel border border-border rounded-lg p-4 min-h-[104px]">
      <div className="text-[#64748B] text-xs font-mono uppercase tracking-widest">{label}</div>
      <div
        className={[
          "mt-3 text-[#F1F5F9] font-semibold",
          compact ? "text-sm font-mono truncate" : "text-2xl",
        ].join(" ")}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-[#64748B] text-xs">{sub}</div>}
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
        "px-3 py-2 rounded-md border border-border text-xs font-mono transition-colors",
        disabled
          ? "text-[#475569] cursor-not-allowed"
          : "text-[#CBD5E1] hover:bg-[#111827]",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function historyExportRows(history) {
  return history.map((row) => flattenForCsv(row));
}

function caseExportRows(summary) {
  return (summary?.cases || []).map((row) => flattenForCsv(row));
}

function HistoryChart({ history }) {
  const rows = [...history].reverse().map((row, index) => ({
    run: index + 1,
    recall: Math.round((row.recall_at_k || 0) * 100),
    mrr: Number(row.mean_reciprocal_rank || 0),
  }));
  if (rows.length === 0) return null;
  return (
    <section className="bg-panel border border-border rounded-lg p-5">
      <h2 className="text-sm font-semibold text-[#F1F5F9]">Retrieval Trend</h2>
      <div className="mt-4 h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" vertical={false} />
            <XAxis dataKey="run" stroke="#64748B" tickLine={false} />
            <YAxis
              stroke="#64748B"
              tickLine={false}
              yAxisId="left"
              tickFormatter={(value) => `${value}%`}
            />
            <YAxis stroke="#64748B" tickLine={false} yAxisId="right" orientation="right" domain={[0, 1]} />
            <Tooltip contentStyle={{ background: "#111118", border: "1px solid #1E1E2E" }} />
            <Line yAxisId="left" dataKey="recall" stroke="#22C55E" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="right" dataKey="mrr" stroke="#3B82F6" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
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
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const [data, historyData] = await Promise.all([
          getRetrievalSummary(),
          getRetrievalHistory(12),
        ]);
        if (!cancelled) {
          setSummary(data);
          setHistory(historyData?.history || []);
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

  const cases = summary?.cases || [];
  const historyRows = historyExportRows(history);
  const casesRows = caseExportRows(summary);

  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-[#F1F5F9] font-semibold text-lg">Retrieval Eval</h1>
          <p className="text-[#64748B] text-sm mt-1">
            Labeled RAG cases for checking citation evidence quality and no-lookahead behavior.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ExportButton
            disabled={loading || !summary}
            onClick={() => downloadJson("retrieval-summary", summary)}
          >
            JSON
          </ExportButton>
          <ExportButton
            disabled={loading || casesRows.length === 0}
            onClick={() => downloadCsv("retrieval-cases", casesRows)}
          >
            Cases CSV
          </ExportButton>
          <ExportButton
            disabled={loading || historyRows.length === 0}
            onClick={() => downloadCsv("retrieval-history", historyRows)}
          >
            History CSV
          </ExportButton>
        </div>
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
            <Metric label="Recall@K" value={pct(summary?.recall_at_k)} />
            <Metric label="MRR" value={summary?.mean_reciprocal_rank || 0} />
            <Metric label="Hits" value={`${summary?.hit_count || 0}/${summary?.case_count || 0}`} />
            <Metric label="Case File" value={summary?.case_file || "n/a"} compact />
          </div>

          <HistoryChart history={history} />

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
              {cases.length === 0 ? (
                <div className="py-5 text-sm text-[#64748B]">No retrieval cases returned.</div>
              ) : (
                cases.map((row) => (
                  <CaseRow key={row.name} row={row} />
                ))
              )}
            </div>
          </section>

          <section className="bg-panel border border-border rounded-lg overflow-x-auto">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-[#F1F5F9]">Recorded Runs</h2>
            </div>
            <div className="px-5 min-w-[760px]">
              <div className="grid grid-cols-[1.4fr_110px_110px_110px_120px] gap-3 py-3 text-xs font-mono uppercase tracking-widest text-[#64748B] border-b border-border">
                <div>Run</div>
                <div>Cases</div>
                <div>Hits</div>
                <div>Recall</div>
                <div>MRR</div>
              </div>
              {history.length === 0 ? (
                <div className="py-5 text-sm text-[#64748B]">
                  No recorded retrieval runs yet. Run eval_retrieval.py with --record.
                </div>
              ) : (
                history.map((row, index) => (
                  <div
                    key={`${row.ran_at}-${index}`}
                    className="grid grid-cols-[1.4fr_110px_110px_110px_120px] gap-3 py-3 border-b border-border last:border-b-0 text-sm"
                  >
                    <div>
                      <div className="text-[#F1F5F9]">{row.ran_at ? new Date(row.ran_at).toLocaleString() : "n/a"}</div>
                      <div className="text-[#64748B] text-xs font-mono truncate">{row.case_file}</div>
                    </div>
                    <div className="text-[#CBD5E1]">{row.case_count}</div>
                    <div className="text-[#CBD5E1]">{row.hit_count}</div>
                    <div className="text-[#22C55E]">{pct(row.recall_at_k)}</div>
                    <div className="text-[#CBD5E1]">{row.mean_reciprocal_rank}</div>
                  </div>
                ))
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
