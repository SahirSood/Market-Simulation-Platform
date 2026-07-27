export default function LiveBadge({ connected }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-600">
      <span className={`h-2 w-2 rounded-full ${connected ? "bg-pnl-green" : "bg-slate-400"}`} />
      <span
        className={`font-medium ${
          connected ? "text-slate-700" : "text-slate-500"
        }`}
      >
        {connected ? "Live · read only" : "Reconnecting"}
      </span>
    </div>
  );
}
