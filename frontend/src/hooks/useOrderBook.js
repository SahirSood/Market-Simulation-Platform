import { useCallback, useEffect, useRef, useState } from "react";
import { getOrderBook } from "../api/endpoints";

const POLL_INTERVAL = 2_000;

function payloadChanged(current, next) {
  return JSON.stringify(current) !== JSON.stringify(next);
}

export function useOrderBook() {
  const [orderBook, setOrderBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const dataRef = useRef(null);
  const inFlightRef = useRef(false);

  const fetchOrderBook = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    if (dataRef.current === null) setLoading(true);
    else setRefreshing(true);

    try {
      const data = await getOrderBook();
      if (!Array.isArray(data)) {
        setError("Live updates are temporarily unavailable");
        return;
      }

      setError(null);
      dataRef.current = data;
      setOrderBook((current) => (payloadChanged(current, data) ? data : current));
      setLastUpdated(Date.now());
    } finally {
      setLoading(false);
      setRefreshing(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    fetchOrderBook();
    const timer = setInterval(fetchOrderBook, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchOrderBook]);

  return {
    orderBook,
    loading,
    refreshing,
    error,
    lastUpdated,
    refetch: fetchOrderBook,
  };
}
