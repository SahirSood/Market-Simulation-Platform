"""
Entry point for the AI Trading Arena bot engine.

Usage:
    python main.py

Starts 10 AI bots (5 personalities x 2 providers) + 10 noise traders
against the C++ matching engine.
Bots make decisions every 20 minutes; noise traders fire every 15 minutes.
All decisions are logged to PostgreSQL (or decisions_fallback.jsonl on DB failure).
Ctrl+C / SIGTERM triggers a clean shutdown.

Prerequisites:
    1. Build the C++ engine:  cmake --build build/
    2. Set up .env with ANTHROPIC_API_KEY (or OPENAI_API_KEY), NEWS_API_KEY, DATABASE_URL
"""
import logging
import signal
import sys
import os
from pathlib import Path

# Add the compiled C++ engine to the Python path.
# The .pyd lives in engine/build/Debug/ relative to this file's parent.
_ENGINE_DIR = Path(__file__).parent.parent / "engine" / "build" / "Debug"
if _ENGINE_DIR.exists():
    sys.path.insert(0, str(_ENGINE_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# ── Imports ───────────────────────────────────────────────────────────────────
from price_feed    import PriceFeed
from news_feed     import NewsFeed
from engine_adapter import EngineAdapter
from noise_traders import NoiseTraderPool
from reasoning_log import ReasoningLog
from scheduler     import BotScheduler
from config        import DATABASE_URL
from rag.repository import RagRepository
from rag.embeddings import get_openai_embedding_service_from_env
from agent_tools   import MarketAgentToolServer
from risk          import RiskLimits
from replay        import ReplayStore

from bots import BearBot, DegenBot, AnalystBot, ContrarianBot, MacroBot


_BOT_CLASSES = [
    BearBot,
    DegenBot,
    AnalystBot,
    ContrarianBot,
    MacroBot,
]
_LIVE_PROVIDERS = ["claude", "openai"]


def _label_provider(provider: str) -> str:
    return "Claude" if provider == "claude" else "OpenAI"


def _make_bot(
    bot_cls,
    price_feed,
    news_feed,
    provider: str,
    rag_repository=None,
    embedding_service=None,
    agent_tool_server=None,
):
    kwargs = {
        "rag_repository": rag_repository,
        "embedding_service": embedding_service,
    }
    if bot_cls is AnalystBot:
        kwargs["agent_tool_server"] = agent_tool_server
    bot = bot_cls(price_feed, news_feed, provider, **kwargs)
    bot.base_name = bot.name
    bot.name = f"{bot.name} ({_label_provider(provider)})"
    bot.bot_id = f"{bot.bot_id}-{provider}"
    return bot


def build_bots(
    price_feed,
    news_feed,
    rag_repository=None,
    embedding_service=None,
    agent_tool_server=None,
) -> list:
    bots = []
    for provider in _LIVE_PROVIDERS:
        for bot_cls in _BOT_CLASSES:
            bots.append(_make_bot(
                bot_cls,
                price_feed,
                news_feed,
                provider,
                rag_repository=rag_repository,
                embedding_service=embedding_service,
                agent_tool_server=agent_tool_server,
            ))
    return bots


def main() -> None:
    logger.info("=" * 60)
    logger.info("AI TRADING ARENA — starting up")
    logger.info("=" * 60)

    price_feed     = PriceFeed()
    news_feed      = NewsFeed()
    engine_adapter = EngineAdapter()
    reasoning_log  = ReasoningLog()   # reads DATABASE_URL from .env
    risk_limits = RiskLimits()
    replay_store = ReplayStore(DATABASE_URL)
    logger.info("Replay/evaluation store initialized")

    rag_repository = None
    embedding_service = None
    try:
        if DATABASE_URL:
            rag_repository = RagRepository(DATABASE_URL)
            rag_repository.create_tables()
            embedding_service = get_openai_embedding_service_from_env()
            logger.info("RAG repository initialized")
    except Exception as e:
        logger.warning(f"RAG initialization skipped: {e}")

    agent_tool_server = MarketAgentToolServer(
        price_feed=price_feed,
        engine_adapter=engine_adapter,
        rag_repository=rag_repository,
        embedding_service=embedding_service,
        risk_limits=risk_limits,
    )

    bots       = build_bots(
        price_feed,
        news_feed,
        rag_repository=rag_repository,
        embedding_service=embedding_service,
        agent_tool_server=agent_tool_server,
    )
    agent_tool_server.set_bots(bots)
    noise_pool = NoiseTraderPool(price_feed, engine_adapter, n_traders=10)
    scheduler  = BotScheduler(
        bots,
        noise_pool,
        engine_adapter,
        reasoning_log,
        risk_limits=risk_limits,
    )

    # ── Clean shutdown on Ctrl+C or SIGTERM ───────────────────────────────────
    def _shutdown(signum, frame):
        logger.info(f"Signal {signum} received — shutting down cleanly…")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    scheduler.start()

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    logger.info(f"Bots: {[b.name for b in bots]}")
    logger.info(
        "Providers: "
        + ", ".join(f"{bot.name}={bot.llm_provider}" for bot in bots)
    )
    logger.info(f"Noise traders: {noise_pool.trader_count}")

    # Keep the main thread alive — scheduler runs on daemon threads
    import time
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
