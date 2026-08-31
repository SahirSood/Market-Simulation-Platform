import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Navigate, Routes, Route, useLocation } from "react-router-dom";
import Navbar from "./components/layout/Navbar";
import { trackPageView } from "./lib/analytics";

const BriefPage = lazy(() => import("./pages/BriefPage"));
const ArenaPage = lazy(() => import("./pages/ArenaPage"));
const ResearchHubPage = lazy(() => import("./pages/ResearchHubPage"));

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
              <Route path="/brief" element={<BriefPage />} />
              <Route path="/research" element={<ResearchHubPage />} />
              <Route path="/retrieval" element={<Navigate to="/research?tab=evidence" replace />} />
              <Route path="/eval" element={<Navigate to="/research?tab=evaluation" replace />} />
              <Route path="/bots" element={<Navigate to="/research?tab=bots" replace />} />
              <Route path="/book" element={<Navigate to="/research?tab=book" replace />} />
              <Route path="/behavior" element={<Navigate to="/research?tab=behavior" replace />} />
              <Route path="/config" element={<Navigate to="/research?tab=config" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  );
}
