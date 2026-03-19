import { useState, useEffect } from "react";
import { getBotDetail, getBotReasoning } from "../api/endpoints";

/**
 * Fetches /bots/{id} (positions + recent decisions) and /bot/{id}/reasoning
 * only when botId is non-null. Used by BotDrawer on open.
 */
export function useBotDetail(botId) {
  const [detail,    setDetail]    = useState(null);
  const [reasoning, setReasoning] = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);

  useEffect(() => {
    if (!botId) {
      setDetail(null);
      setReasoning([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([getBotDetail(botId), getBotReasoning(botId)]).then(
      ([d, r]) => {
        if (cancelled) return;
        if (!d) { setError("Failed to load bot detail"); }
        else     { setDetail(d); setReasoning(r || []); }
        setLoading(false);
      }
    );

    return () => { cancelled = true; };
  }, [botId]);

  return { detail, reasoning, loading, error };
}
