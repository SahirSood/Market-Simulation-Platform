import { useEffect, useMemo, useState } from "react";
import { startSandbox, stopSandbox } from "../api/endpoints";
import OrderBookPanel from "../components/book/OrderBookPanel";
import Skeleton from "../components/ui/Skeleton";
import { useOrderBook } from "../hooks/useOrderBook";
import { useWebSocket } from "../hooks/useWebSocket";

function formatElapsed(elapsed) {
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function ErrorBanner({ error, onRetry }) {
  return (
    <div className="flex items-center gap-3 bg-rose-50 border border-rose-200 rounded-xl px-5 py-3 text-left text-sm">
      <span className="text-rose-600">{error}</span>
      {onRetry && (
        <button onClick={onRetry} className="ml-auto text-xs font-mono text-rose-600 underline">
          Retry
        </button>
      )}
    </div>
  );
}

function SandboxOrderBook() {
  const { orderBook, loading, error, refetch } = useOrderBook();
  const snapshot = orderBook?.[0] ?? null;

  return (
    <div className="mt-4 w-full rounded-xl border border-border bg-panel p-6 text-left">
      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((row) => (
            <Skeleton key={row} className="h-6 w-full" />
          ))}
        </div>
      ) : error ? (
        <ErrorBanner error="Unable to load order book" onRetry={refetch} />
      ) : !snapshot ? (
        <p className="font-mono text-sm text-slate-500">Waiting for first orders...</p>
      ) : (
        <OrderBookPanel snapshot={snapshot} />
      )}
    </div>
  );
}

export default function SandboxPage() {
  const { events } = useWebSocket();
  const [apiKey, setApiKey] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [sandboxTradeCount, setSandboxTradeCount] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [sessionStartedAt, setSessionStartedAt] = useState(null);

  useEffect(() => {
    const storedKey = localStorage.getItem("arena_api_key");
    if (storedKey) setApiKey(storedKey);
  }, []);

  useEffect(() => {
    localStorage.setItem("arena_api_key", apiKey);
  }, [apiKey]);

  useEffect(() => {
    if (!isActive) return undefined;
    const timer = setInterval(() => {
      setElapsed((current) => current + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [isActive]);

  const liveSandboxTradeCount = useMemo(() => {
    return events.filter((event) => {
      if (event.sandbox !== true || event.type !== "trade") return false;
      if (!sessionStartedAt) return false;
      return new Date(event.timestamp).getTime() >= sessionStartedAt;
    }).length;
  }, [events, sessionStartedAt]);

  useEffect(() => {
    if (!isActive) return;
    setSandboxTradeCount(liveSandboxTradeCount);
  }, [isActive, liveSandboxTradeCount]);

  async function handleStart() {
    setError("");
    const result = await startSandbox(apiKey);
    if (!result) {
      setError("Unable to start sandbox");
      return;
    }
    setElapsed(0);
    setSandboxTradeCount(0);
    setSessionStartedAt(Date.now());
    setIsActive(true);
  }

  async function handleStop() {
    setError("");
    const result = await stopSandbox(apiKey);
    if (!result) {
      setError("Unable to stop sandbox");
      return;
    }
    setIsActive(false);
    setSessionStartedAt(null);
  }

  return (
    <div className="mx-auto max-w-[640px] px-6 py-16 text-center">
      <div className="space-y-6">
        {error && <ErrorBanner error={error} />}

        {!isActive ? (
          <>
            <div>
              <h1 className="text-xl font-semibold text-ink">SANDBOX MODE</h1>
              <p className="mt-2 text-sm text-slate-500">
                Test the matching engine with simulated traders.
                <br />
                No LLM calls. No real data. Pure engine mechanics.
              </p>
            </div>

            <div className="mt-8 text-left">
              <label className="mb-1 block text-[10px] font-mono uppercase tracking-widest text-slate-500">
                API KEY
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="w-full rounded-2xl border border-border bg-white px-4 py-2.5 font-mono text-sm text-ink shadow-sm focus:border-claude focus:outline-none"
                placeholder="Enter API key"
              />
            </div>

            <button
              onClick={handleStart}
              className="mt-6 flex w-full items-center justify-center gap-3 rounded-2xl bg-emerald-50 py-4 font-mono text-base font-semibold tracking-wide text-emerald-700 ring-1 ring-emerald-200 transition-colors hover:bg-emerald-100"
            >
              <span className="text-xl">&gt;</span>
              START SANDBOX
            </button>
          </>
        ) : (
          <>
            <div className="mb-6 flex items-center justify-center">
              <span className="h-2 w-2 rounded-full bg-pnl-green animate-pulse" />
              <span className="ml-2 font-mono text-sm font-bold text-emerald-600">
                SANDBOX ACTIVE
              </span>
            </div>

            <div className="mb-6 flex justify-center gap-6 font-mono text-sm text-slate-500">
              <span>
                Trades: <span className="text-ink">{sandboxTradeCount}</span>
              </span>
              <span>
                Elapsed: <span className="text-ink">{formatElapsed(elapsed)}</span>
              </span>
            </div>

            <SandboxOrderBook />

            <button
              onClick={handleStop}
              className="mt-6 flex w-full items-center justify-center gap-3 rounded-2xl bg-rose-50 py-4 font-mono text-base font-semibold tracking-wide text-rose-700 ring-1 ring-rose-200 transition-colors hover:bg-rose-100"
            >
              <span className="text-xl">[]</span>
              STOP SANDBOX
            </button>
          </>
        )}
      </div>
    </div>
  );
}
