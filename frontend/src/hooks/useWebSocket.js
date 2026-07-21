import { useState, useEffect, useRef, useCallback } from "react";
import { BASE } from "../api/client";

const WS_URL = BASE.replace(/^http/, "ws") + "/ws/live";
const MAX_EVENTS = 50;
const RECONNECT_DELAY = 3000;

export function useWebSocket() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (mountedRef.current) setConnected(true);
      };

      ws.onmessage = (e) => {
        if (!mountedRef.current) return;
        try {
          const event = JSON.parse(e.data);
          setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS));
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        // Auto-reconnect after 3 seconds
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // WebSocket not available; schedule reconnect.
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { events, connected };
}
