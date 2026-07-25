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


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    values = tuple(
        part.strip().upper()
        for part in raw_value.split(",")
        if part.strip()
    )
    return values or default


# Cache TTLs
PRICE_CACHE_TTL = _int_env("PRICE_CACHE_TTL", 60)
NEWS_CACHE_TTL = _int_env("NEWS_CACHE_TTL", 600)

# Competition parameters
STARTING_CASH = _float_env("STARTING_CASH", 100_000.0)
BOT_CYCLE_MINS = _float_env("BOT_CYCLE_MINS", 60)
NOISE_INTERVAL = _float_env("NOISE_INTERVAL", 900)
MM_INTERVAL = _float_env("MM_INTERVAL", 30)

# Market-hours gate for live hosted cost control.
MARKET_HOURS_ONLY = _bool_env("MARKET_HOURS_ONLY", True)
MARKET_TIMEZONE = os.getenv("MARKET_TIMEZONE", "America/New_York")
MARKET_OPEN_TIME = os.getenv("MARKET_OPEN_TIME", "09:30")
MARKET_CLOSE_TIME = os.getenv("MARKET_CLOSE_TIME", "16:00")

# LLM prompt/cost controls.
LLM_MAX_TOKENS = _int_env("LLM_MAX_TOKENS", 160)
LLM_PROMPT_CACHE_ENABLED = _bool_env("LLM_PROMPT_CACHE_ENABLED", True)
LLM_SKIP_UNCHANGED_PROMPTS = _bool_env("LLM_SKIP_UNCHANGED_PROMPTS", True)
LLM_COST_GUARD_ENABLED = _bool_env("LLM_COST_GUARD_ENABLED", True)
LLM_DAILY_DECISION_BUDGET = _int_env("LLM_DAILY_DECISION_BUDGET", 70)
LLM_MONTHLY_DECISION_BUDGET = _int_env("LLM_MONTHLY_DECISION_BUDGET", 1200)
LLM_CLAUDE_DAILY_CALL_BUDGET = _int_env("LLM_CLAUDE_DAILY_CALL_BUDGET", 0)
LLM_CLAUDE_MONTHLY_CALL_BUDGET = _int_env("LLM_CLAUDE_MONTHLY_CALL_BUDGET", 0)
LLM_OPENAI_DAILY_CALL_BUDGET = _int_env("LLM_OPENAI_DAILY_CALL_BUDGET", 0)
LLM_OPENAI_MONTHLY_CALL_BUDGET = _int_env("LLM_OPENAI_MONTHLY_CALL_BUDGET", 0)
LLM_DAILY_SPEND_LIMIT_USD = _float_env("LLM_DAILY_SPEND_LIMIT_USD", 1.0)
LLM_MONTHLY_SPEND_LIMIT_USD = _float_env("LLM_MONTHLY_SPEND_LIMIT_USD", 20.0)
LLM_FALLBACK_ESTIMATED_COST_PER_CALL_USD = _float_env("LLM_FALLBACK_ESTIMATED_COST_PER_CALL_USD", 0.02)
LLM_ESTIMATED_INPUT_TOKENS_PER_CALL = _int_env("LLM_ESTIMATED_INPUT_TOKENS_PER_CALL", 1200)
LLM_ESTIMATED_OUTPUT_TOKENS_PER_CALL = _int_env("LLM_ESTIMATED_OUTPUT_TOKENS_PER_CALL", LLM_MAX_TOKENS)
LLM_OPENAI_INPUT_COST_PER_1M_TOKENS = _float_env("LLM_OPENAI_INPUT_COST_PER_1M_TOKENS", 0.15)
LLM_OPENAI_OUTPUT_COST_PER_1M_TOKENS = _float_env("LLM_OPENAI_OUTPUT_COST_PER_1M_TOKENS", 0.60)
LLM_CLAUDE_INPUT_COST_PER_1M_TOKENS = _float_env("LLM_CLAUDE_INPUT_COST_PER_1M_TOKENS", 1.00)
LLM_CLAUDE_OUTPUT_COST_PER_1M_TOKENS = _float_env("LLM_CLAUDE_OUTPUT_COST_PER_1M_TOKENS", 5.00)
PROMPT_TRENDING_LIMIT = _int_env("PROMPT_TRENDING_LIMIT", 6)
PROMPT_RECENT_LIMIT = _int_env("PROMPT_RECENT_LIMIT", 6)
PROMPT_TICKER_LIMIT = _int_env("PROMPT_TICKER_LIMIT", 4)
PROMPT_TICKER_HEADLINE_LIMIT = _int_env("PROMPT_TICKER_HEADLINE_LIMIT", 1)
PROMPT_EVIDENCE_LIMIT = _int_env("PROMPT_EVIDENCE_LIMIT", 2)
PROMPT_EVIDENCE_CHARS = _int_env("PROMPT_EVIDENCE_CHARS", 120)
EVIDENCE_QUERY_HEADLINE_LIMIT = _int_env("EVIDENCE_QUERY_HEADLINE_LIMIT", 2)

# Live demo trading universe and order-book seeding.
TRADABLE_TICKERS = _csv_env(
    "TRADABLE_TICKERS",
    ("AAPL", "MSFT", "NVDA", "GOOGL", "TSLA", "SPY", "QQQ", "TLT", "GLD", "IEF"),
)
SEED_LIQUIDITY_ON_STARTUP = _bool_env("SEED_LIQUIDITY_ON_STARTUP", True)
SEED_LIQUIDITY_LEVELS = _int_env("SEED_LIQUIDITY_LEVELS", 3)
SEED_LIQUIDITY_QTY = _int_env("SEED_LIQUIDITY_QTY", 500)
SEED_LIQUIDITY_SPREAD_PCT = _float_env("SEED_LIQUIDITY_SPREAD_PCT", 0.002)

# RAG decision support.
RAG_TOP_K = _int_env("RAG_TOP_K", 2)
RAG_MIN_EVIDENCE_SCORE = _float_env("RAG_MIN_EVIDENCE_SCORE", 0.15)
RAG_REQUIRE_EVIDENCE_FOR_TRADES = _bool_env("RAG_REQUIRE_EVIDENCE_FOR_TRADES", True)
RAG_EVIDENCE_REQUIRED_BOTS = _csv_env("RAG_EVIDENCE_REQUIRED_BOTS", ("ANALYSTBOT", "MACROBOT"))
RAG_SPECULATIVE_BOTS = _csv_env("RAG_SPECULATIVE_BOTS", ("DEGENBOT",))

# Startup/bootstrap ingestion defaults.
RAG_BOOTSTRAP_ON_STARTUP = _bool_env("RAG_BOOTSTRAP_ON_STARTUP", True)
RAG_BOOTSTRAP_TICKERS = _csv_env("RAG_BOOTSTRAP_TICKERS", ("AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"))
RAG_BOOTSTRAP_FORMS = _csv_env("RAG_BOOTSTRAP_FORMS", ("10-K", "10-Q", "8-K"))
RAG_BOOTSTRAP_MAX_FILINGS = _int_env("RAG_BOOTSTRAP_MAX_FILINGS", 1)
RAG_BOOTSTRAP_MAX_RETRIES = _int_env("RAG_BOOTSTRAP_MAX_RETRIES", 1)
RAG_BOOTSTRAP_EMBED_LIMIT = _int_env("RAG_BOOTSTRAP_EMBED_LIMIT", 1500)
RAG_BOOTSTRAP_EMBED_BATCH_SIZE = _int_env("RAG_BOOTSTRAP_EMBED_BATCH_SIZE", 64)
RAG_BOOTSTRAP_BOT_DELAY_SECS = _float_env("RAG_BOOTSTRAP_BOT_DELAY_SECS", 120)

# Bot-requested research ingestion.
RESEARCH_AUTO_INGEST_ENABLED = _bool_env("RESEARCH_AUTO_INGEST_ENABLED", True)
RESEARCH_TRIGGER_ACTIONS = _csv_env("RESEARCH_TRIGGER_ACTIONS", ("BUY", "SELL"))
RESEARCH_MAX_TICKERS_PER_DAY = _int_env("RESEARCH_MAX_TICKERS_PER_DAY", 25)
RESEARCH_TICKER_COOLDOWN_MINS = _float_env("RESEARCH_TICKER_COOLDOWN_MINS", 60)
RESEARCH_MAX_TICKERS_PER_CONTEXT = _int_env("RESEARCH_MAX_TICKERS_PER_CONTEXT", 4)
RESEARCH_MAX_FILINGS_PER_TICKER = _int_env("RESEARCH_MAX_FILINGS_PER_TICKER", 1)
RESEARCH_FORMS = _csv_env("RESEARCH_FORMS", ("10-K", "10-Q", "8-K"))
RESEARCH_EMBED_LIMIT = _int_env("RESEARCH_EMBED_LIMIT", 500)
RESEARCH_EMBED_BATCH_SIZE = _int_env("RESEARCH_EMBED_BATCH_SIZE", 64)
RESEARCH_EXPAND_TRADABLE_UNIVERSE = _bool_env("RESEARCH_EXPAND_TRADABLE_UNIVERSE", True)

# Experimental Phase C path: direct prompts remain the default.
ANALYST_AGENT_TOOLS_ENABLED = _bool_env("ANALYST_AGENT_TOOLS_ENABLED", False)
