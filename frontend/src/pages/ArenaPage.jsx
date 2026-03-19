import ComparisonChart from "../components/arena/ComparisonChart";
import StatBar        from "../components/ui/StatBar";
import LiveFeed       from "../components/arena/LiveFeed";

export default function ArenaPage() {
  return (
    <div className="max-w-[1280px] mx-auto px-6 py-8 space-y-6">
      <ComparisonChart />
      <StatBar />
      <LiveFeed />
    </div>
  );
}
