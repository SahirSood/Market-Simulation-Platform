import { useEffect, useState } from "react";

import { getDecisionBrief } from "../api/endpoints";
import ComparisonChart from "../components/arena/ComparisonChart";
import StatBar        from "../components/ui/StatBar";
import LiveFeed       from "../components/arena/LiveFeed";
import ResearchPulse  from "../components/arena/ResearchPulse";
import AgentActivity  from "../components/arena/AgentActivity";
import GlossaryFAQ    from "../components/arena/GlossaryFAQ";
import MarketOverview from "../components/arena/MarketOverview";
import TradingSnapshot from "../components/arena/TradingSnapshot";

export default function ArenaPage() {
  const [ticker, setTicker] = useState("NVDA");
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const result = await getDecisionBrief({ ticker, includeEvidence: false });
      if (!cancelled) {
        setBrief(result);
        setError(result ? null : "Market and benchmark context is temporarily unavailable.");
        setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [ticker]);

  return (
    <div className="mx-auto max-w-[1320px] space-y-5 px-4 py-6 md:space-y-6 md:px-8 md:py-8">
      <MarketOverview data={brief} ticker={ticker} onTickerChange={setTicker} loading={loading} error={error} />
      <StatBar />
      <ComparisonChart />
      <TradingSnapshot ticker={ticker} />
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <LiveFeed />
        <div className="space-y-6">
          <ResearchPulse />
          <AgentActivity />
        </div>
      </div>
      <GlossaryFAQ />
    </div>
  );
}
