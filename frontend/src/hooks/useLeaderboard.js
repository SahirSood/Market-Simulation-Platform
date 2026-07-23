import { useState, useEffect, useRef } from "react";
import { getLeaderboard } from "../api/endpoints";

const POLL_INTERVAL = 30_000;

export function useLeaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const timerRef = useRef(null);

  async function fetchLeaderboard() {
    setLoading((current) => current && leaderboard.length === 0);
    const data = await getLeaderboard();
    if (!data) {
      setError("Failed to load leaderboard");
      setLoading(false);
      return;
    }
    setError(null);
    setLeaderboard(Array.isArray(data) ? data : []);
    setLoading(false);
  }

  useEffect(() => {
    fetchLeaderboard();
    timerRef.current = setInterval(fetchLeaderboard, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, []);

  return { leaderboard, loading, error, refetch: fetchLeaderboard };
}
