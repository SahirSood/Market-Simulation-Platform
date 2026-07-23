import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/layout/Navbar";
import ArenaPage   from "./pages/ArenaPage";
import BotsPage    from "./pages/BotsPage";
import BookPage    from "./pages/BookPage";
import EvalPage    from "./pages/EvalPage";
import BehaviorPage from "./pages/BehaviorPage";
import RetrievalPage from "./pages/RetrievalPage";
import ConfigPage from "./pages/ConfigPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg/80 font-sans text-ink">
        <Navbar />
        <main className="pt-28 sm:pt-20 md:pt-16">
          <Routes>
            <Route path="/"        element={<ArenaPage />}   />
            <Route path="/bots"    element={<BotsPage />}    />
            <Route path="/book"    element={<BookPage />}    />
            <Route path="/behavior" element={<BehaviorPage />} />
            <Route path="/eval"    element={<EvalPage />}    />
            <Route path="/retrieval" element={<RetrievalPage />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="*" element={<ArenaPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
