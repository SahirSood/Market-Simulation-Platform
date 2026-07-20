import { apiFetch } from "./client";

export const getBots        = ()      => apiFetch("/bots");
export const getBotDetail   = (id)    => apiFetch(`/bots/${id}`);
export const getLeaderboard = ()      => apiFetch("/leaderboard");
export const getOrderBook   = ()      => apiFetch("/orderbook");
export const getTrades      = ()      => apiFetch("/trades");
export const getBotReasoning= (id, limit = 200) => apiFetch(`/bot/${id}/reasoning?limit=${limit}`);
export const getEvaluationSummary = (limit = 500) =>
  apiFetch(`/evaluation/summary?limit=${limit}`);
export const getBotBehavior = (limit = 1000) =>
  apiFetch(`/evaluation/bot-behavior?limit=${limit}`);
export const getBotBehaviorDetail = (id, limit = 500) =>
  apiFetch(`/evaluation/bot-behavior/${id}?limit=${limit}`);
export const getRiskRejections = (limit = 100) =>
  apiFetch(`/evaluation/risk-rejections?limit=${limit}`);
export const getEvidenceChunks = (chunkIds) => {
  const ids = [...new Set((chunkIds || []).filter((id) => id !== null && id !== undefined))];
  if (ids.length === 0) {
    return Promise.resolve({ requested_ids: [], chunks: [], missing_ids: [] });
  }
  return apiFetch(`/evaluation/evidence?chunk_ids=${ids.join(",")}`);
};
export const getReplayRuns = () => apiFetch("/evaluation/replay-runs");
export const getReplayRun = (id, decisionLimit = 500) =>
  apiFetch(`/evaluation/replay-runs/${id}?decision_limit=${decisionLimit}`);
export const getReplayRunComparison = ({ fingerprint = null, runId = null } = {}) => {
  const params = new URLSearchParams();
  if (fingerprint) params.set("fingerprint", fingerprint);
  if (runId) params.set("run_id", runId);
  return apiFetch(`/evaluation/replay-runs/compare?${params.toString()}`);
};
export const getReplayRunDecisions = (id, limit = 500, botId = null) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (botId) params.set("bot_id", botId);
  return apiFetch(`/evaluation/replay-runs/${id}/decisions?${params.toString()}`);
};
export const getRetrievalSummary = ({ caseFile = "sec_basic_cases.json", topK = null } = {}) => {
  const params = new URLSearchParams({ case_file: caseFile });
  if (topK) params.set("top_k", String(topK));
  return apiFetch(`/evaluation/retrieval-summary?${params.toString()}`);
};
export const getRetrievalHistory = (limit = 20) =>
  apiFetch(`/evaluation/retrieval-history?limit=${limit}`);
export const getModelConfig = () => apiFetch("/config/models");
export const getRiskLimits = () => apiFetch("/config/risk-limits");
export const getRagStatus = () => apiFetch("/ops/rag/status");
export const getIngestionStatus = () => apiFetch("/ops/ingestion/status");

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
