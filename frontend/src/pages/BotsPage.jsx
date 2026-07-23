import { useState } from "react";
import BotCard from "../components/bots/BotCard";
import BotDrawer from "../components/bots/BotDrawer";
import InfoTooltip from "../components/ui/InfoTooltip";
import Skeleton from "../components/ui/Skeleton";
import { useBots } from "../hooks/useBots";

function TeamColumn({ label, color, bots, onSelect }) {
  return (
    <div className="min-w-0 flex-1 space-y-3">
      <div className="flex items-center gap-2 pb-1">
        <div className="h-4 w-1 rounded-full" style={{ backgroundColor: color }} />
        <h2 className="text-xs font-mono font-bold uppercase tracking-widest" style={{ color }}>
          {label}
        </h2>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-mono font-bold text-slate-500">
          {bots.length}
        </span>
      </div>

      {bots.map((bot) => (
        <BotCard key={bot.bot_id} bot={bot} onSelect={onSelect} />
      ))}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {[0, 1].map((col) => (
        <div key={col} className="space-y-3">
          <Skeleton className="h-5 w-24" />
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-[24px]" />
          ))}
        </div>
      ))}
    </div>
  );
}

const QUICK_GUIDE = [
  ["Degen", "High-conviction momentum bot. It can make speculative market orders."],
  ["Analyst", "Evidence-first bot. It prefers SEC-supported limit orders."],
  ["Bear", "Risk-off bot. It sells or holds; it does not buy."],
  ["Contrarian", "Fades crowded moves and looks for reversals."],
  ["Macro", "Trades broad ETFs around macroeconomic signals."],
];

export default function BotsPage() {
  const { claudeBots, gptBots, loading, error, refetch } = useBots();
  const [selectedBot, setSelectedBot] = useState(null);

  return (
    <div className="mx-auto max-w-[1280px] px-3 py-4 sm:px-4 md:px-6 md:py-8">
      <div className="mb-6">
        <div className="flex items-center gap-1">
          <h1 className="text-2xl font-black tracking-tight text-ink">Bots</h1>
          <InfoTooltip label="What is a bot personality?">
            A personality is a fixed trading style prompt and risk profile. Claude and OpenAI each run the same five
            personalities so viewers can compare behavior without changing the rules.
          </InfoTooltip>
        </div>
        <p className="mt-1 text-sm text-slate-600">
          10 active traders: 5 Claude, 5 OpenAI. Click any card to inspect trades, reasoning, and evidence.
        </p>
      </div>

      <details className="mb-6 rounded-lg border border-border bg-white px-4 py-3 shadow-sm">
        <summary className="cursor-pointer list-none text-sm font-bold text-ink">
          Quick personality guide
        </summary>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {QUICK_GUIDE.map(([term, definition]) => (
            <div key={term} className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="font-mono text-xs font-bold text-ink">{term}</div>
              <p className="mt-1 text-xs leading-5 text-slate-600">{definition}</p>
            </div>
          ))}
        </div>
      </details>

      {error ? (
        <div className="mb-4 flex items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm">
          <span className="text-sm text-rose-700">{error}</span>
          <button onClick={refetch} className="ml-auto text-xs font-mono text-rose-700 underline">
            Retry
          </button>
        </div>
      ) : null}

      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <TeamColumn label="Claude" color="#2563EB" bots={claudeBots} onSelect={setSelectedBot} />
          <TeamColumn label="OpenAI" color="#F97316" bots={gptBots} onSelect={setSelectedBot} />
        </div>
      )}

      {selectedBot ? <BotDrawer bot={selectedBot} onClose={() => setSelectedBot(null)} /> : null}
    </div>
  );
}
