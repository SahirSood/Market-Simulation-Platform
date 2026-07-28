import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import Navbar from "./components/layout/Navbar";
import { trackPageView } from "./lib/analytics";

const ArenaPage = lazy(() => import("./pages/ArenaPage"));
const BotsPage = lazy(() => import("./pages/BotsPage"));
const BookPage = lazy(() => import("./pages/BookPage"));
const BehaviorPage = lazy(() => import("./pages/BehaviorPage"));
const EvalPage = lazy(() => import("./pages/EvalPage"));
const RetrievalPage = lazy(() => import("./pages/RetrievalPage"));
const ConfigPage = lazy(() => import("./pages/ConfigPage"));

function RouteFallback() {
  return (
    <div className="mx-auto max-w-[1320px] px-4 py-6 md:px-8 md:py-8">
      <div className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <div className="animate-pulse space-y-4">
          <div className="h-5 w-48 rounded bg-slate-200" />
          <div className="h-64 rounded-lg bg-slate-100" />
        </div>
      </div>
    </div>
  );
}

function AnalyticsTracker() {
  const location = useLocation();

  useEffect(() => {
    trackPageView(`${location.pathname}${location.search}`);
  }, [location.pathname, location.search]);

  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <AnalyticsTracker />
      <div className="min-h-screen bg-bg font-sans text-ink">
        <Navbar />
        <main className="pt-28 md:pt-16">
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<ArenaPage />} />
              <Route path="/bots" element={<BotsPage />} />
              <Route path="/book" element={<BookPage />} />
              <Route path="/behavior" element={<BehaviorPage />} />
              <Route path="/eval" element={<EvalPage />} />
              <Route path="/retrieval" element={<RetrievalPage />} />
              <Route path="/config" element={<ConfigPage />} />
              <Route path="*" element={<ArenaPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  );
}
