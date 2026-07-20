import ComparisonChart from "../components/arena/ComparisonChart";
import StatBar        from "../components/ui/StatBar";
import LiveFeed       from "../components/arena/LiveFeed";
import ResearchPulse  from "../components/arena/ResearchPulse";

export default function ArenaPage() {
  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <ComparisonChart />
      <StatBar />
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <LiveFeed />
        <ResearchPulse />
      </div>
    </div>
  );
}
