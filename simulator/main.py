"""
Entry point for the AI Trading Arena bot engine.

Usage:
    python main.py

Starts all 5 AI bots + 10 noise traders against the C++ matching engine.
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

from bots import BearBot, DegenBot, AnalystBot, ContrarianBot, MacroBot


def build_bots(price_feed, news_feed, llm_provider: str = "claude") -> list:
    return [
        BearBot(price_feed,       news_feed, llm_provider),
        DegenBot(price_feed,      news_feed, llm_provider),
        AnalystBot(price_feed,    news_feed, llm_provider),
        ContrarianBot(price_feed, news_feed, llm_provider),
        MacroBot(price_feed,      news_feed, llm_provider),
    ]


def main() -> None:
    logger.info("=" * 60)
    logger.info("AI TRADING ARENA — starting up")
    logger.info("=" * 60)

    price_feed     = PriceFeed()
    news_feed      = NewsFeed()
    engine_adapter = EngineAdapter()
    reasoning_log  = ReasoningLog()   # reads DATABASE_URL from .env

    bots       = build_bots(price_feed, news_feed, llm_provider="claude")
    noise_pool = NoiseTraderPool(price_feed, engine_adapter, n_traders=10)
    scheduler  = BotScheduler(bots, noise_pool, engine_adapter, reasoning_log)

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
    logger.info(f"Noise traders: {noise_pool.trader_count}")

    # Keep the main thread alive — scheduler runs on daemon threads
    signal.pause()


if __name__ == "__main__":
    main()
