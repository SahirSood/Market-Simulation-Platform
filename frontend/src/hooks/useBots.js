import { useState, useEffect, useRef } from "react";
import { getBots } from "../api/endpoints";

const POLL_INTERVAL = 30_000;

export function useBots() {
  const [claudeBots, setClaudeBots] = useState([]);
  const [gptBots, setGptBots]       = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const timerRef = useRef(null);

  async function fetchBots() {
    setLoading(true);
    const data = await getBots();
    if (!data) {
      setError("Failed to load bots");
      setLoading(false);
      return;
    }
    setError(null);
    const bots = Array.isArray(data) ? data : Object.values(data);
    setClaudeBots(bots.filter((b) => b.llm_provider === "claude"));
    setGptBots(bots.filter((b) => b.llm_provider === "openai"));
    setLoading(false);
  }

  useEffect(() => {
    fetchBots();
    timerRef.current = setInterval(fetchBots, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, []);

  return { claudeBots, gptBots, loading, error, refetch: fetchBots };
}
