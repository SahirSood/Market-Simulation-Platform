export default function ArenaPage() {
  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">

      {/* ComparisonChart placeholder */}
      <div className="bg-panel border border-border rounded-xl p-6 h-[480px] flex items-center justify-center">
        <div className="text-center space-y-2">
          <div className="text-4xl">📈</div>
          <p className="text-[#64748B] text-sm font-mono">
            ComparisonChart — coming in Page 2
          </p>
        </div>
      </div>

      {/* StatBar placeholder */}
      <div className="bg-panel border border-border rounded-xl py-3 px-6 flex items-center gap-2">
        <span className="text-[#64748B] text-sm font-mono">
          StatBar — coming in Page 3
        </span>
      </div>

      {/* LiveFeed placeholder */}
      <div className="bg-panel border border-border rounded-xl p-6 h-64 flex items-center justify-center">
        <p className="text-[#64748B] text-sm font-mono">
          LiveFeed — coming in Page 3
        </p>
      </div>

    </div>
  );
}
