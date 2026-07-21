export default function LiveBadge({ connected }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 shadow-sm">
      <span className="relative flex h-2 w-2">
        <span
          className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
            connected ? "bg-pnl-green" : "bg-slate-400"
          }`}
        />
        <span
          className={`relative inline-flex rounded-full h-2 w-2 ${
            connected ? "bg-pnl-green" : "bg-slate-400"
          }`}
        />
      </span>
      <span
        className={`text-xs font-mono font-semibold tracking-widest ${
          connected ? "text-pnl-green" : "text-slate-400"
        }`}
      >
        LIVE
      </span>
    </div>
  );
}
