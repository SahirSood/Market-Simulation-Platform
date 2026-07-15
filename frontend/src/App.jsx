import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/layout/Navbar";
import ArenaPage   from "./pages/ArenaPage";
import BotsPage    from "./pages/BotsPage";
import BookPage    from "./pages/BookPage";
import SandboxPage from "./pages/SandboxPage";
import EvalPage    from "./pages/EvalPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg font-sans">
        <Navbar />
        <main className="pt-14">
          <Routes>
            <Route path="/"        element={<ArenaPage />}   />
            <Route path="/bots"    element={<BotsPage />}    />
            <Route path="/book"    element={<BookPage />}    />
            <Route path="/eval"    element={<EvalPage />}    />
            <Route path="/sandbox" element={<SandboxPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
