import { apiFetch } from "./client";

export const getBots        = ()      => apiFetch("/bots");
export const getBotDetail   = (id)    => apiFetch(`/bots/${id}`);
export const getLeaderboard = ()      => apiFetch("/leaderboard");
export const getOrderBook   = ()      => apiFetch("/orderbook");
export const getTrades      = ()      => apiFetch("/trades");
export const getBotReasoning= (id)    => apiFetch(`/bot/${id}/reasoning`);

export const startSandbox = (apiKey) =>
  apiFetch("/sandbox/start", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
  });

export const stopSandbox = (apiKey) =>
  apiFetch("/sandbox/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
  });
