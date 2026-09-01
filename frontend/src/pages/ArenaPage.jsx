import { useEffect, useState } from "react";

import { getDecisionBrief, getLiveEvaluationReport } from "../api/endpoints";
import ComparisonChart from "../components/arena/ComparisonChart";
import StatBar        from "../components/ui/StatBar";
import LiveFeed       from "../components/arena/LiveFeed";
import ResearchPulse  from "../components/arena/ResearchPulse";
import AgentActivity  from "../components/arena/AgentActivity";
import AgentReadout   from "../components/arena/AgentReadout";
import GlossaryFAQ    from "../components/arena/GlossaryFAQ";
import MarketOverview from "../components/arena/MarketOverview";
import TradingSnapshot from "../components/arena/TradingSnapshot";

export default function ArenaPage() {
  const [ticker, setTicker] = useState("NVDA");
  const [brief, setBrief] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [evaluationLoading, setEvaluationLoading] = useState(true);
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

  useEffect(() => {
    let cancelled = false;
    async function loadEvaluation() {
      const result = await getLiveEvaluationReport({ periodDays: 7, minSamples: 50, horizon: "1d" });
      if (!cancelled) {
        setEvaluation(result);
        setEvaluationLoading(false);
      }
    }
    loadEvaluation();
    const timer = setInterval(loadEvaluation, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="mx-auto max-w-[1320px] space-y-5 px-4 py-6 md:space-y-6 md:px-8 md:py-8">
      <ComparisonChart evaluation={evaluation} />
      <AgentReadout report={evaluation} loading={evaluationLoading} />
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <LiveFeed />
        <AgentActivity />
      </div>
      <StatBar />
      <TradingSnapshot ticker={ticker} />
      <MarketOverview data={brief} ticker={ticker} onTickerChange={setTicker} loading={loading} error={error} />
      <ResearchPulse />
      <GlossaryFAQ />
    </div>
  );
}
