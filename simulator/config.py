# All config lives here — never hardcode values elsewhere
import os
from dotenv import load_dotenv

load_dotenv()

# API keys — loaded from .env, never committed to source control
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY")
DATABASE_URL      = os.getenv("DATABASE_URL")

# LLM model identifiers — both bots run same personalities, different providers
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
OPENAI_MODEL = "gpt-4o-mini"

# Cache TTLs
PRICE_CACHE_TTL = 60    # seconds — prices change tick-by-tick, 60s is stale enough to not spam yfinance
NEWS_CACHE_TTL  = 300   # seconds — headlines don't change per-minute, 5 min avoids NewsAPI rate limits

# Competition parameters
STARTING_CASH   = 100_000  # each bot starts with $100k
BOT_CYCLE_MINS  = 20       # how often AI bots make decisions (20 min = 3× per hour)
NOISE_INTERVAL  = 900      # seconds between noise trader cycles
MM_INTERVAL     = 30       # seconds between market maker quote refresh

# RAG decision support
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_MIN_EVIDENCE_SCORE = float(os.getenv("RAG_MIN_EVIDENCE_SCORE", "0.15"))
