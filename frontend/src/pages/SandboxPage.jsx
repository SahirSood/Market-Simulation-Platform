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
    <div className="flex items-center gap-3 bg-[#450A0A] border border-[#EF4444]/30 rounded-xl px-5 py-3 text-left text-sm">
      <span className="text-[#EF4444]">{error}</span>
      {onRetry && (
        <button onClick={onRetry} className="ml-auto text-xs font-mono text-[#EF4444] underline">
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
        <p className="font-mono text-sm text-[#64748B]">Waiting for first orders...</p>
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
              <h1 className="text-xl font-semibold text-[#F1F5F9]">SANDBOX MODE</h1>
              <p className="mt-2 text-sm text-[#64748B]">
                Test the matching engine with simulated traders.
                <br />
                No LLM calls. No real data. Pure engine mechanics.
              </p>
            </div>

            <div className="mt-8 text-left">
              <label className="mb-1 block text-[10px] font-mono uppercase tracking-widest text-[#64748B]">
                API KEY
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="w-full rounded-lg border border-border bg-panel px-4 py-2.5 font-mono text-sm text-[#F1F5F9] focus:border-[#3B82F6] focus:outline-none"
                placeholder="Enter API key"
              />
            </div>

            <button
              onClick={handleStart}
              className="mt-6 flex w-full items-center justify-center gap-3 rounded-xl bg-[#14532D] py-4 font-mono text-base font-semibold tracking-wide text-[#22C55E] transition-colors hover:bg-[#166534]"
            >
              <span className="text-xl">&gt;</span>
              START SANDBOX
            </button>
          </>
        ) : (
          <>
            <div className="mb-6 flex items-center justify-center">
              <span className="h-2 w-2 rounded-full bg-[#22C55E] animate-pulse" />
              <span className="ml-2 font-mono text-sm font-bold text-[#22C55E]">
                SANDBOX ACTIVE
              </span>
            </div>

            <div className="mb-6 flex justify-center gap-6 font-mono text-sm text-[#64748B]">
              <span>
                Trades: <span className="text-[#F1F5F9]">{sandboxTradeCount}</span>
              </span>
              <span>
                Elapsed: <span className="text-[#F1F5F9]">{formatElapsed(elapsed)}</span>
              </span>
            </div>

            <SandboxOrderBook />

            <button
              onClick={handleStop}
              className="mt-6 flex w-full items-center justify-center gap-3 rounded-xl bg-[#450A0A] py-4 font-mono text-base font-semibold tracking-wide text-[#EF4444] transition-colors hover:bg-[#7F1D1D]"
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
