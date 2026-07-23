import ComparisonChart from "../components/arena/ComparisonChart";
import StatBar        from "../components/ui/StatBar";
import LiveFeed       from "../components/arena/LiveFeed";
import ResearchPulse  from "../components/arena/ResearchPulse";
import AgentActivity  from "../components/arena/AgentActivity";
import GlossaryFAQ    from "../components/arena/GlossaryFAQ";

export default function ArenaPage() {
  return (
    <div className="mx-auto max-w-[1320px] space-y-5 px-3 py-4 sm:px-4 md:space-y-6 md:px-6 md:py-8">
      <ComparisonChart />
      <StatBar />
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
