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
          <div className="text-[#F1F5F9] text-sm font-semibold">
            {chunk.ticker || "Unknown"} {chunk.form_type || "Filing"}
          </div>
          <div className="mt-1 text-[#64748B] text-xs font-mono">
            chunk {chunk.chunk_id} | doc {chunk.document_id} | {formatDate(chunk.published_at)}
          </div>
        </div>
        {chunk.source_url && (
          <a
            href={chunk.source_url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs text-claude hover:text-[#93C5FD]"
          >
            Source
          </a>
        )}
      </div>

      <div className="mt-3 text-[#CBD5E1] text-sm leading-6 whitespace-pre-wrap">
        {chunk.content}
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-mono text-[#64748B]">
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
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      <aside className="absolute right-0 top-0 h-full w-full max-w-[560px] bg-panel border-l border-border shadow-2xl flex flex-col">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
          <div>
            <h2 className="text-[#F1F5F9] font-semibold text-base">Evidence</h2>
            <div className="mt-1 text-[#64748B] text-xs">
              Cited RAG chunks and filing metadata
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-[#CBD5E1] hover:text-[#F1F5F9] hover:border-[#334155]"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6">
          {loading && (
            <div className="py-6 text-sm text-[#64748B]">Loading cited chunks...</div>
          )}

          {error && (
            <div className="my-5 bg-[#450A0A] border border-[#EF4444]/30 rounded-lg px-4 py-3 text-sm text-[#EF4444]">
              {error}
            </div>
          )}

          {!loading && !error && chunks.length === 0 && (
            <div className="py-6 text-sm text-[#64748B]">
              No matching evidence chunks were found.
            </div>
          )}

          {!loading && !error && chunks.map((chunk) => (
            <EvidenceRow key={chunk.chunk_id} chunk={chunk} />
          ))}

          {!loading && !error && missing.length > 0 && (
            <div className="my-5 rounded-lg border border-[#F97316]/30 bg-[#431407] px-4 py-3 text-sm text-[#FDBA74]">
              Missing chunk ids: {missing.join(", ")}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
