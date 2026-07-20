# All config lives here — never hardcode values elsewhere
import os
from dotenv import load_dotenv

load_dotenv()

# API keys — loaded from .env, never committed to source control
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY")
DATABASE_URL      = os.getenv("DATABASE_URL")

# LLM model identifiers. Env overrides keep replay/config comparisons reproducible.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "phase-d-v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return float(raw_value.replace("_", "").replace(",", ""))
    except ValueError:
        return default


# Cache TTLs
PRICE_CACHE_TTL = 60    # seconds — prices change tick-by-tick, 60s is stale enough to not spam yfinance
NEWS_CACHE_TTL  = 300   # seconds — headlines don't change per-minute, 5 min avoids NewsAPI rate limits

# Competition parameters
STARTING_CASH   = _float_env("STARTING_CASH", 100_000.0)  # each bot starts with $100k by default
BOT_CYCLE_MINS  = 20       # how often AI bots make decisions (20 min = 3× per hour)
NOISE_INTERVAL  = 900      # seconds between noise trader cycles
MM_INTERVAL     = 30       # seconds between market maker quote refresh

# RAG decision support
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_MIN_EVIDENCE_SCORE = float(os.getenv("RAG_MIN_EVIDENCE_SCORE", "0.15"))

# Experimental Phase C path: direct prompts remain the default.
ANALYST_AGENT_TOOLS_ENABLED = os.getenv("ANALYST_AGENT_TOOLS_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
