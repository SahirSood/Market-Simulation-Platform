import { Suspense, lazy, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import Skeleton from "../components/ui/Skeleton";

const RetrievalPage = lazy(() => import("./RetrievalPage"));
const EvalPage = lazy(() => import("./EvalPage"));
const BotsPage = lazy(() => import("./BotsPage"));
const BookPage = lazy(() => import("./BookPage"));
const BehaviorPage = lazy(() => import("./BehaviorPage"));
const ConfigPage = lazy(() => import("./ConfigPage"));

const TABS = [
  { id: "evidence", label: "Evidence", component: RetrievalPage },
  { id: "evaluation", label: "Evaluation", component: EvalPage },
  { id: "bots", label: "Bots", component: BotsPage },
  { id: "book", label: "Order Book", component: BookPage },
  { id: "behavior", label: "Behavior", component: BehaviorPage },
  { id: "config", label: "Config", component: ConfigPage },
];

export default function ResearchHubPage() {
  const [params, setParams] = useSearchParams();
  const activeId = params.get("tab") || "evidence";
  const active = useMemo(
    () => TABS.find((tab) => tab.id === activeId) || TABS[0],
    [activeId],
  );
  const ActiveComponent = active.component;

  function setTab(id) {
    setParams({ tab: id });
  }

  return (
    <div>
      <div className="border-b border-border bg-white">
        <div className="mx-auto max-w-[1320px] px-4 py-4 md:px-8">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-slate-500">
                Research Workbench
              </div>
              <h1 className="mt-1 text-xl font-semibold tracking-tight text-ink">Supporting Data</h1>
            </div>
            <div className="flex gap-1 overflow-x-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setTab(tab.id)}
                  className={[
                    "whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                    active.id === tab.id
                      ? "border-ink text-ink"
                      : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-900",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <Suspense fallback={<div className="mx-auto max-w-[1320px] px-4 py-6 md:px-8"><Skeleton className="h-[420px]" /></div>}>
        <ActiveComponent />
      </Suspense>
    </div>
  );
}
