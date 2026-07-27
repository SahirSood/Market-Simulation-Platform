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
  const inFlightRef = useRef(false);
  const idsKey = botIds.join(",");

  useEffect(() => {
    if (!botIds.length) {
      setReasoningMap(new Map());
      setLoading(false);
      return;
    }

    const activeIds = idsKey ? idsKey.split(",") : [];

    async function fetchAll() {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      const results = await Promise.all(
        activeIds.map((id) => getBotReasoning(id, limit).catch(() => null))
      );
      setReasoningMap((current) => {
        const next = new Map(current);
        let changed = false;
        for (const id of next.keys()) {
          if (!activeIds.includes(id)) {
            next.delete(id);
            changed = true;
          }
        }
        activeIds.forEach((id, i) => {
          const entries = results[i];
          if (!Array.isArray(entries)) return;
          const series = entries
            .filter((e) => e?.portfolio_snapshot?.total_value != null)
            .map((e) => ({
              timestamp: e.timestamp,
              value: e.portfolio_snapshot.total_value,
            }))
            .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
          if (JSON.stringify(current.get(id) || []) !== JSON.stringify(series)) {
            next.set(id, series);
            changed = true;
          }
        });
        return changed ? next : current;
      });
      setLoading(false);
      inFlightRef.current = false;
    }

    fetchAll();
    const timer = setInterval(fetchAll, POLL_INTERVAL);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey, limit]);

  return { reasoningMap, loading };
}
