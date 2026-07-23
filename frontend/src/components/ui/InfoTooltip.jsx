export default function InfoTooltip({ label, children }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-300 bg-white font-mono text-[11px] font-bold text-slate-500 shadow-sm transition-colors hover:border-slate-400 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-claude/30"
      >
        ?
      </button>
      <span className="pointer-events-none absolute right-0 top-7 z-40 hidden w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-white p-3 text-left text-xs leading-5 text-slate-600 shadow-xl shadow-slate-200/80 group-hover:block group-focus-within:block sm:left-1/2 sm:right-auto sm:-translate-x-1/2">
        {children}
      </span>
    </span>
  );
}
