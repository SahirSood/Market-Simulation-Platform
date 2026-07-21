function formatDate(value) {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function EvidenceRow({ chunk }) {
  return (
    <div className="border-b border-border last:border-b-0 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-ink text-sm font-semibold">
            {chunk.ticker || "Unknown"} {chunk.form_type || "Filing"}
          </div>
          <div className="mt-1 text-slate-500 text-xs font-mono">
            chunk {chunk.chunk_id} | doc {chunk.document_id} | {formatDate(chunk.published_at)}
          </div>
        </div>
        {chunk.source_url && (
          <a
            href={chunk.source_url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs text-claude hover:text-blue-500"
          >
            Source
          </a>
        )}
      </div>

      <div className="mt-3 text-slate-700 text-sm leading-6 whitespace-pre-wrap">
        {chunk.content}
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-mono text-slate-500">
        {chunk.accession_no && <span>{chunk.accession_no}</span>}
        {chunk.source_name && <span>{chunk.source_name}</span>}
        {chunk.start_pos !== null && chunk.start_pos !== undefined && (
          <span>
            {chunk.start_pos}-{chunk.end_pos}
          </span>
        )}
      </div>
    </div>
  );
}

export default function EvidenceDrawer({ open, loading, error, data, onClose }) {
  if (!open) return null;

  const chunks = data?.chunks || [];
  const missing = data?.missing_ids || [];

  return (
    <div className="fixed inset-0 z-[80]">
      <button
        type="button"
        aria-label="Close evidence drawer"
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[560px] flex-col border-l border-border bg-white shadow-2xl shadow-slate-400/30">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
          <div>
            <h2 className="text-ink font-semibold text-base">Evidence</h2>
            <div className="mt-1 text-slate-500 text-xs">
              Cited RAG chunks and filing metadata
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border px-3 py-1.5 text-sm text-slate-700 hover:border-slate-300 hover:text-ink"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6">
          {loading && (
            <div className="py-6 text-sm text-slate-500">Loading cited chunks...</div>
          )}

          {error && (
            <div className="my-5 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3 text-sm text-rose-600">
              {error}
            </div>
          )}

          {!loading && !error && chunks.length === 0 && (
            <div className="py-6 text-sm text-slate-500">
              No matching evidence chunks were found.
            </div>
          )}

          {!loading && !error && chunks.map((chunk) => (
            <EvidenceRow key={chunk.chunk_id} chunk={chunk} />
          ))}

          {!loading && !error && missing.length > 0 && (
            <div className="my-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              Missing chunk ids: {missing.join(", ")}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
