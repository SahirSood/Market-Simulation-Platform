# All config lives here. Never hardcode values elsewhere.
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API keys are loaded from .env or deployment secrets, never committed to source control.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
LOCAL_FALLBACK_DATABASE_PATH = os.getenv(
    "LOCAL_FALLBACK_DATABASE_PATH",
    "data/marketsim-fallback.db",
)


def local_fallback_database_url() -> str:
    """Return a writable local SQLite URL for degraded hosted operation."""
    path = Path(LOCAL_FALLBACK_DATABASE_PATH).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve().as_posix()}"

# LLM model identifiers. Env overrides keep replay/config comparisons reproducible.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "competitive-v2")
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


def _csv_env_preserve(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    values = tuple(
        part.strip()
        for part in raw_value.split(",")
        if part.strip()
    )
    return values or default


def _choice_env(name: str, default: str, choices: set[str]) -> str:
    value = str(os.getenv(name, default) or default).strip().lower()
    return value if value in choices else default


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
LLM_MAX_TOKENS = _int_env("LLM_MAX_TOKENS", 800)
OPENAI_REASONING_EFFORT = _choice_env(
    "OPENAI_REASONING_EFFORT",
    "medium",
    {"none", "low", "medium", "high", "xhigh", "max"},
)
CLAUDE_EFFORT = _choice_env(
    "CLAUDE_EFFORT",
    "medium",
    {"low", "medium", "high", "xhigh", "max"},
)
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
LLM_FALLBACK_ESTIMATED_COST_PER_CALL_USD = _float_env("LLM_FALLBACK_ESTIMATED_COST_PER_CALL_USD", 0.016)
LLM_ESTIMATED_INPUT_TOKENS_PER_CALL = _int_env("LLM_ESTIMATED_INPUT_TOKENS_PER_CALL", 1200)
LLM_ESTIMATED_OUTPUT_TOKENS_PER_CALL = _int_env("LLM_ESTIMATED_OUTPUT_TOKENS_PER_CALL", LLM_MAX_TOKENS)
LLM_OPENAI_INPUT_COST_PER_1M_TOKENS = _float_env("LLM_OPENAI_INPUT_COST_PER_1M_TOKENS", 0.75)
LLM_OPENAI_OUTPUT_COST_PER_1M_TOKENS = _float_env("LLM_OPENAI_OUTPUT_COST_PER_1M_TOKENS", 4.50)
LLM_CLAUDE_INPUT_COST_PER_1M_TOKENS = _float_env("LLM_CLAUDE_INPUT_COST_PER_1M_TOKENS", 3.00)
LLM_CLAUDE_OUTPUT_COST_PER_1M_TOKENS = _float_env("LLM_CLAUDE_OUTPUT_COST_PER_1M_TOKENS", 15.00)
PROMPT_TRENDING_LIMIT = _int_env("PROMPT_TRENDING_LIMIT", 6)
PROMPT_RECENT_LIMIT = _int_env("PROMPT_RECENT_LIMIT", 6)
PROMPT_TICKER_LIMIT = _int_env("PROMPT_TICKER_LIMIT", 9)
PROMPT_TICKER_HEADLINE_LIMIT = _int_env("PROMPT_TICKER_HEADLINE_LIMIT", 1)
PROMPT_EVIDENCE_LIMIT = _int_env("PROMPT_EVIDENCE_LIMIT", 2)
PROMPT_EVIDENCE_CHARS = _int_env("PROMPT_EVIDENCE_CHARS", 320)
EVIDENCE_QUERY_HEADLINE_LIMIT = _int_env("EVIDENCE_QUERY_HEADLINE_LIMIT", 2)

# Focused trading-arena universe and benchmark context.
TRADABLE_TICKERS = _csv_env(
    "TRADABLE_TICKERS",
    ("NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA"),
)
BENCHMARK_TICKERS = _csv_env(
    "BENCHMARK_TICKERS",
    ("SPY", "QQQ"),
)
SEED_LIQUIDITY_ON_STARTUP = _bool_env("SEED_LIQUIDITY_ON_STARTUP", True)
SEED_LIQUIDITY_LEVELS = _int_env("SEED_LIQUIDITY_LEVELS", 3)
SEED_LIQUIDITY_QTY = _int_env("SEED_LIQUIDITY_QTY", 500)
SEED_LIQUIDITY_SPREAD_PCT = _float_env("SEED_LIQUIDITY_SPREAD_PCT", 0.002)

# RAG decision support.
RAG_TOP_K = _int_env("RAG_TOP_K", 2)
RAG_MIN_EVIDENCE_SCORE = _float_env("RAG_MIN_EVIDENCE_SCORE", 0.15)
RAG_REQUIRE_EVIDENCE_FOR_TRADES = _bool_env("RAG_REQUIRE_EVIDENCE_FOR_TRADES", True)
RAG_EVIDENCE_REQUIRED_BOTS = _csv_env("RAG_EVIDENCE_REQUIRED_BOTS", ("ANALYSTBOT",))
RAG_SPECULATIVE_BOTS = _csv_env("RAG_SPECULATIVE_BOTS", ("DEGENBOT",))

# The scheduler and MCP tools share this deterministic risk setting.
SHORT_SELLING_ENABLED = _bool_env("SHORT_SELLING_ENABLED", True)

# Startup/bootstrap ingestion defaults.
RAG_BOOTSTRAP_ON_STARTUP = _bool_env("RAG_BOOTSTRAP_ON_STARTUP", True)
RAG_BOOTSTRAP_TICKERS = _csv_env(
    "RAG_BOOTSTRAP_TICKERS",
    ("NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "AMZN", "TSLA"),
)
RAG_BOOTSTRAP_FORMS = _csv_env("RAG_BOOTSTRAP_FORMS", ("10-K", "10-Q", "8-K"))
RAG_BOOTSTRAP_MAX_FILINGS = _int_env("RAG_BOOTSTRAP_MAX_FILINGS", 1)
RAG_BOOTSTRAP_MAX_RETRIES = _int_env("RAG_BOOTSTRAP_MAX_RETRIES", 1)
RAG_BOOTSTRAP_EMBED_LIMIT = _int_env("RAG_BOOTSTRAP_EMBED_LIMIT", 1500)
RAG_BOOTSTRAP_EMBED_BATCH_SIZE = _int_env("RAG_BOOTSTRAP_EMBED_BATCH_SIZE", 64)
RAG_BOOTSTRAP_BOT_DELAY_SECS = _float_env("RAG_BOOTSTRAP_BOT_DELAY_SECS", 120)
RAG_STARTUP_RESET_ID = os.getenv("RAG_STARTUP_RESET_ID", "").strip()
RAG_STARTUP_RESET_TICKERS = _csv_env("RAG_STARTUP_RESET_TICKERS", ())

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
RESEARCH_EXPAND_TRADABLE_UNIVERSE = _bool_env("RESEARCH_EXPAND_TRADABLE_UNIVERSE", False)

# Experimental Phase C path: direct prompts remain the default.
ANALYST_AGENT_TOOLS_ENABLED = _bool_env("ANALYST_AGENT_TOOLS_ENABLED", False)

# Cheap evaluation work can run on a background cadence. Replay matrices remain
# opt-in because they call model providers and can spend tokens.
EVALUATION_SCHEDULER_ENABLED = _bool_env("EVALUATION_SCHEDULER_ENABLED", True)
EVALUATION_SCHEDULER_STARTUP_DELAY_SECS = _float_env(
    "EVALUATION_SCHEDULER_STARTUP_DELAY_SECS",
    60.0,
)
OUTCOME_LABELING_ENABLED = _bool_env("OUTCOME_LABELING_ENABLED", True)
OUTCOME_LABELING_INTERVAL_MINS = _float_env("OUTCOME_LABELING_INTERVAL_MINS", 60.0)
OUTCOME_LABELING_HORIZONS = _csv_env_preserve(
    "OUTCOME_LABELING_HORIZONS",
    ("1h", "6h", "1d", "7d"),
)
OUTCOME_LABELING_DECISION_LIMIT = _int_env("OUTCOME_LABELING_DECISION_LIMIT", 2000)
# The live report reads stored rows only. It stays monitoring-only until the
# selected outcome horizon reaches the configured label threshold.
LIVE_EVALUATION_REPORT_ENABLED = _bool_env("LIVE_EVALUATION_REPORT_ENABLED", True)
LIVE_EVALUATION_REPORT_INTERVAL_HOURS = _float_env(
    "LIVE_EVALUATION_REPORT_INTERVAL_HOURS",
    168.0,
)
LIVE_EVALUATION_REPORT_STARTUP_DELAY_SECS = _float_env(
    "LIVE_EVALUATION_REPORT_STARTUP_DELAY_SECS",
    120.0,
)
LIVE_EVALUATION_REPORT_LOOKBACK_DAYS = _int_env("LIVE_EVALUATION_REPORT_LOOKBACK_DAYS", 7)
LIVE_EVALUATION_REPORT_MIN_SAMPLES = _int_env("LIVE_EVALUATION_REPORT_MIN_SAMPLES", 50)
LIVE_EVALUATION_REPORT_DECISION_LIMIT = _int_env("LIVE_EVALUATION_REPORT_DECISION_LIMIT", 10000)
LIVE_EVALUATION_REPORT_HORIZON = os.getenv("LIVE_EVALUATION_REPORT_HORIZON", "1d").strip().lower()
LIVE_EVALUATION_REPORT_DIR = os.getenv(
    "LIVE_EVALUATION_REPORT_DIR",
    str(Path(__file__).resolve().parents[1] / "data" / "live_evaluation"),
)
REPLAY_MATRIX_SCHEDULE_ENABLED = _bool_env("REPLAY_MATRIX_SCHEDULE_ENABLED", False)
REPLAY_MATRIX_INTERVAL_HOURS = _float_env("REPLAY_MATRIX_INTERVAL_HOURS", 24.0)
REPLAY_MATRIX_STARTUP_DELAY_SECS = _float_env("REPLAY_MATRIX_STARTUP_DELAY_SECS", 300.0)
REPLAY_MATRIX_FIXTURES = _csv_env_preserve(
    "REPLAY_MATRIX_FIXTURES",
    ("sample_earnings_beat.json",),
)
REPLAY_MATRIX_PROVIDER_SETS = _csv_env_preserve(
    "REPLAY_MATRIX_PROVIDER_SETS",
    ("claude", "openai"),
)
REPLAY_MATRIX_BOTS = _csv_env_preserve("REPLAY_MATRIX_BOTS", ("analyst", "bear", "macro"))
REPLAY_MATRIX_EXECUTE_ORDERS = _bool_env("REPLAY_MATRIX_EXECUTE_ORDERS", False)
REPLAY_MATRIX_MAX_FIXTURES_PER_RUN = _int_env("REPLAY_MATRIX_MAX_FIXTURES_PER_RUN", 1)
