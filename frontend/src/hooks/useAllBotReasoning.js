import { useState, useEffect, useRef } from "react";
import { getBotReasoning } from "../api/endpoints";

const POLL_INTERVAL = 30_000;

/**
 * Fetches /bot/{id}/reasoning for every bot ID in the array.
 * Returns reasoningMap: Map<botId, [{timestamp, value}]>
 * Points are sorted oldest-first and filtered to only entries with portfolio_snapshot.total_value.
 */
export function useAllBotReasoning(botIds, limit = 500) {
  const [reasoningMap, setReasoningMap] = useState(new Map());
  const [loading, setLoading]           = useState(true);
  const timerRef = useRef(null);
  const idsKey = botIds.join(",");

  useEffect(() => {
    if (!botIds.length) {
      setReasoningMap(new Map());
      setLoading(false);
      return;
    }

    async function fetchAll() {
      setLoading(true);
      const results = await Promise.all(
        botIds.map((id) => getBotReasoning(id, limit).catch(() => []))
      );
      const map = new Map();
      botIds.forEach((id, i) => {
        const entries = results[i] || [];
        const series = entries
          .filter((e) => e?.portfolio_snapshot?.total_value != null)
          .map((e) => ({
            timestamp: e.timestamp,
            value: e.portfolio_snapshot.total_value,
          }))
          .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        map.set(id, series);
      });
      setReasoningMap(map);
      setLoading(false);
    }

    fetchAll();
    timerRef.current = setInterval(fetchAll, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey, limit]);

  return { reasoningMap, loading };
}
