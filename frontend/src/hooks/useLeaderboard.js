import { useCallback, useEffect, useRef, useState } from "react";
import { getLeaderboard } from "../api/endpoints";

const POLL_INTERVAL = 30_000;

export function useLeaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const hasDataRef = useRef(false);
  const inFlightRef = useRef(false);

  const fetchLeaderboard = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    if (!hasDataRef.current) setLoading(true);

    try {
      const data = await getLeaderboard();
      if (!data) {
        setError("Failed to load leaderboard");
        return;
      }
      const next = Array.isArray(data) ? data : [];
      setError(null);
      setLeaderboard((current) =>
        JSON.stringify(current) === JSON.stringify(next) ? current : next
      );
      hasDataRef.current = true;
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    fetchLeaderboard();
    const timer = setInterval(fetchLeaderboard, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchLeaderboard]);

  return { leaderboard, loading, error, refetch: fetchLeaderboard };
}
