import { useState, useEffect, useRef } from "react";
import { getOrderBook } from "../api/endpoints";

const POLL_INTERVAL = 2_000;

export function useOrderBook() {
  const [orderBook, setOrderBook] = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const timerRef = useRef(null);

  async function fetchOrderBook() {
    setLoading((current) => current && !orderBook);
    const data = await getOrderBook();
    if (!data) {
      setError("Failed to load order book");
      setLoading(false);
      return;
    }
    setError(null);
    setOrderBook(data);
    setLoading(false);
  }

  useEffect(() => {
    fetchOrderBook();
    timerRef.current = setInterval(fetchOrderBook, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, []);

  return { orderBook, loading, error, refetch: fetchOrderBook };
}
