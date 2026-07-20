# All config lives here. Never hardcode values elsewhere.
import os
from dotenv import load_dotenv

load_dotenv()

# API keys are loaded from .env or deployment secrets, never committed to source control.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

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


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value.replace("_", "").replace(",", ""))
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


# Cache TTLs
PRICE_CACHE_TTL = _int_env("PRICE_CACHE_TTL", 60)
NEWS_CACHE_TTL = _int_env("NEWS_CACHE_TTL", 600)

# Competition parameters
STARTING_CASH = _float_env("STARTING_CASH", 100_000.0)
BOT_CYCLE_MINS = _float_env("BOT_CYCLE_MINS", 60)
NOISE_INTERVAL = _float_env("NOISE_INTERVAL", 900)
MM_INTERVAL = _float_env("MM_INTERVAL", 30)

# LLM prompt/cost controls
LLM_MAX_TOKENS = _int_env("LLM_MAX_TOKENS", 160)
LLM_PROMPT_CACHE_ENABLED = _bool_env("LLM_PROMPT_CACHE_ENABLED", True)
PROMPT_TRENDING_LIMIT = _int_env("PROMPT_TRENDING_LIMIT", 6)
PROMPT_RECENT_LIMIT = _int_env("PROMPT_RECENT_LIMIT", 6)
PROMPT_TICKER_LIMIT = _int_env("PROMPT_TICKER_LIMIT", 1)
PROMPT_TICKER_HEADLINE_LIMIT = _int_env("PROMPT_TICKER_HEADLINE_LIMIT", 1)
PROMPT_EVIDENCE_LIMIT = _int_env("PROMPT_EVIDENCE_LIMIT", 2)
PROMPT_EVIDENCE_CHARS = _int_env("PROMPT_EVIDENCE_CHARS", 120)
EVIDENCE_QUERY_HEADLINE_LIMIT = _int_env("EVIDENCE_QUERY_HEADLINE_LIMIT", 2)

# RAG decision support
RAG_TOP_K = _int_env("RAG_TOP_K", 2)
RAG_MIN_EVIDENCE_SCORE = float(os.getenv("RAG_MIN_EVIDENCE_SCORE", "0.15"))

# Experimental Phase C path: direct prompts remain the default.
ANALYST_AGENT_TOOLS_ENABLED = _bool_env("ANALYST_AGENT_TOOLS_ENABLED", False)
