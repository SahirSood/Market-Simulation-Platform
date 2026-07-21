/**
 * provider: "claude" | "openai"  (or bot_id ending in "-claude" / "-openai")
 */
export default function TeamDot({ provider }) {
  const isClaude = provider?.includes("claude");
  return (
    <span
      className="inline-block w-2 h-2 rounded-full shrink-0 mt-1"
      style={{ backgroundColor: isClaude ? "#2563EB" : "#F97316" }}
      title={isClaude ? "Claude" : "GPT"}
    />
  );
}
