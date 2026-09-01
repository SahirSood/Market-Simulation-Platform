import { useCallback, useEffect, useRef, useState } from "react";
import { getBots } from "../api/endpoints";

const POLL_INTERVAL = 10_000;

export function useBots() {
  const [claudeBots, setClaudeBots] = useState([]);
  const [gptBots, setGptBots]       = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const hasDataRef = useRef(false);
  const inFlightRef = useRef(false);

  const fetchBots = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    if (!hasDataRef.current) setLoading(true);

    try {
      const data = await getBots();
      if (!data) {
        setError("Failed to load bots");
        return;
      }
      setError(null);
      const bots = Array.isArray(data) ? data : Object.values(data);
      const nextClaude = bots.filter((b) => b.llm_provider === "claude");
      const nextOpenAI = bots.filter((b) => b.llm_provider === "openai");
      setClaudeBots((current) =>
        JSON.stringify(current) === JSON.stringify(nextClaude) ? current : nextClaude
      );
      setGptBots((current) =>
        JSON.stringify(current) === JSON.stringify(nextOpenAI) ? current : nextOpenAI
      );
      hasDataRef.current = true;
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    fetchBots();
    const timer = setInterval(fetchBots, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchBots]);

  return { claudeBots, gptBots, loading, error, refetch: fetchBots };
}
