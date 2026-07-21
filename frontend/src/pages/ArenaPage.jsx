import ComparisonChart from "../components/arena/ComparisonChart";
import StatBar        from "../components/ui/StatBar";
import LiveFeed       from "../components/arena/LiveFeed";
import ResearchPulse  from "../components/arena/ResearchPulse";

export default function ArenaPage() {
  return (
    <div className="mx-auto max-w-[1320px] space-y-6 px-4 py-6 md:px-6 md:py-8">
      <ComparisonChart />
      <StatBar />
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <LiveFeed />
        <ResearchPulse />
      </div>
    </div>
  );
}
