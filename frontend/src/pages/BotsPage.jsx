import { useState } from "react";
import { useBots }   from "../hooks/useBots";
import BotCard       from "../components/bots/BotCard";
import BotDrawer     from "../components/bots/BotDrawer";
import Skeleton      from "../components/ui/Skeleton";

function TeamColumn({ label, color, bots, onSelect }) {
  return (
    <div className="flex-1 min-w-0 space-y-3">
      {/* Column header */}
      <div className="flex items-center gap-2 pb-1">
        <div className="w-1 h-4 rounded-full" style={{ backgroundColor: color }} />
        <h2
          className="text-xs font-mono font-bold tracking-widest uppercase"
          style={{ color }}
        >
          {label}
        </h2>
      </div>

      {bots.map((bot) => (
        <BotCard key={bot.bot_id} bot={bot} onSelect={onSelect} />
      ))}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="flex gap-6">
      {[0, 1].map((col) => (
        <div key={col} className="flex-1 space-y-3">
          <Skeleton className="h-5 w-24" />
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
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
    <div className="max-w-[1280px] mx-auto px-6 py-8">

      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-[#F1F5F9] font-semibold text-lg">Bots</h1>
        <p className="text-[#64748B] text-sm mt-1">
          10 active traders — 5 Claude, 5 GPT-4o. Click any card to inspect.
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-3 bg-[#450A0A] border border-[#EF4444]/30 rounded-xl px-5 py-3">
          <span className="text-[#EF4444] text-sm">{error}</span>
          <button
            onClick={refetch}
            className="text-[#EF4444] text-xs font-mono underline ml-auto"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="flex gap-6">
          <TeamColumn
            label="Claude"
            color="#3B82F6"
            bots={claudeBots}
            onSelect={setSelectedBot}
          />
          <TeamColumn
            label="GPT-4o"
            color="#F97316"
            bots={gptBots}
            onSelect={setSelectedBot}
          />
        </div>
      )}

      {/* Drawer — renders even when closed for smooth animation */}
      <BotDrawer
        bot={selectedBot}
        onClose={() => setSelectedBot(null)}
      />

    </div>
  );
}
