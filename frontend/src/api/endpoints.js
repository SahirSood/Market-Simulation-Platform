import { apiFetch } from "./client";

export const getBots        = ()      => apiFetch("/bots");
export const getBotDetail   = (id)    => apiFetch(`/bots/${id}`);
export const getLeaderboard = ()      => apiFetch("/leaderboard");
export const getOrderBook   = ()      => apiFetch("/orderbook");
export const getTrades      = ()      => apiFetch("/trades");
export const getBotReasoning= (id)    => apiFetch(`/bot/${id}/reasoning`);
export const getEvaluationSummary = (limit = 500) =>
  apiFetch(`/evaluation/summary?limit=${limit}`);
export const getReplayRuns = () => apiFetch("/evaluation/replay-runs");
export const getReplayRun = (id, decisionLimit = 500) =>
  apiFetch(`/evaluation/replay-runs/${id}?decision_limit=${decisionLimit}`);
export const getReplayRunDecisions = (id, limit = 500, botId = null) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (botId) params.set("bot_id", botId);
  return apiFetch(`/evaluation/replay-runs/${id}/decisions?${params.toString()}`);
};

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
