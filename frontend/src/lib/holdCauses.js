const HOLD_CAUSE_LABELS = {
  no_edge: "No clear edge",
  weak_evidence: "Weak evidence",
  risk_reward: "Poor risk/reward",
  risk_limit: "Risk limit",
  cost_control: "Cost control",
  market_hours: "Market closed",
  budget: "Decision budget",
  invalid_output: "Invalid model output",
  guardrail: "Safety guardrail",
  error: "Model error",
  unknown: "Unclassified hold",
};

export function holdCauseLabel(cause) {
  const key = String(cause || "unknown").trim().toLowerCase();
  return HOLD_CAUSE_LABELS[key] || "Unclassified hold";
}

export default HOLD_CAUSE_LABELS;
