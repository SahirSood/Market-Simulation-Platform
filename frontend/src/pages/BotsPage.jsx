import { useState } from "react";
import BotCard from "../components/bots/BotCard";
import BotDrawer from "../components/bots/BotDrawer";
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

export default function BotsPage() {
  const { claudeBots, gptBots, loading, error, refetch } = useBots();
  const [selectedBot, setSelectedBot] = useState(null);

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8 md:px-6">
      <div className="mb-6">
        <h1 className="text-2xl font-black tracking-tight text-ink">Bots</h1>
        <p className="mt-1 text-sm text-slate-600">
          10 active traders: 5 Claude, 5 OpenAI. Click any card to inspect trades, reasoning, and evidence.
        </p>
      </div>

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
