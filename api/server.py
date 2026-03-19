"""
AI Trading Arena — FastAPI server entry point.

Run from the project root:
    python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

Or directly:
    python api/server.py
"""
import sys
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# ── Add simulator/ to Python path ─────────────────────────────────────────────
_SIM_DIR    = Path(__file__).parent.parent / "simulator"
_ENGINE_DIR = Path(__file__).parent.parent / "engine" / "build" / "Debug"

for _p in [str(_SIM_DIR), str(_ENGINE_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("server")

# ── Simulator imports ─────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(_SIM_DIR / ".env")  # load simulator/.env

from price_feed     import PriceFeed
from news_feed      import NewsFeed
from engine_adapter import EngineAdapter
from reasoning_log  import ReasoningLog
from noise_traders  import NoiseTraderPool
from scheduler      import BotScheduler
from bots           import BearBot, DegenBot, AnalystBot, ContrarianBot, MacroBot

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


def _make_bot(bot_cls, price_feed, news_feed, provider: str):
    bot = bot_cls(price_feed, news_feed, provider)
    bot.base_name = bot.name
    bot.name = f"{bot.name} ({_label_provider(provider)})"
    bot.bot_id = f"{bot.bot_id}-{provider}"
    return bot

# ── API imports ───────────────────────────────────────────────────────────────
from fastapi import FastAPI
from api import state as app_state
from api.ws_manager import manager as ws_manager
from api.middleware import setup_middleware
from api.routers import bots, market, leaderboard, sandbox, websocket


# ── Lifespan (startup + shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Validate required env vars ────────────────────────────────────────────
    required = ["ANTHROPIC_API_KEY", "DATABASE_URL", "NEWS_API_KEY"]
    missing  = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {missing}")

    logger.info("=" * 60)
    logger.info("AI TRADING ARENA — API server starting")
    logger.info("=" * 60)

    # ── Construct shared objects ───────────────────────────────────────────────
    price_feed     = PriceFeed()
    news_feed      = NewsFeed()
    engine_adapter = EngineAdapter()
    reasoning_log  = ReasoningLog()

    bot_list = []
    for provider in _LIVE_PROVIDERS:
        for bot_cls in _BOT_CLASSES:
            bot_list.append(_make_bot(bot_cls, price_feed, news_feed, provider))
    noise_pool = NoiseTraderPool(price_feed, engine_adapter, n_traders=10)

    # ── Wire WebSocket broadcaster to scheduler ────────────────────────────────
    loop = asyncio.get_event_loop()

    def on_event(payload: dict):
        ws_manager.broadcast_from_thread(payload, loop)

    scheduler = BotScheduler(
        bots           = bot_list,
        noise_pool     = noise_pool,
        engine_adapter = engine_adapter,
        reasoning_log  = reasoning_log,
        event_callback = on_event,
    )
    scheduler.start()

    # ── Populate AppState singleton ────────────────────────────────────────────
    app_state.init(app_state.AppState(
        bots           = bot_list,
        engine_adapter = engine_adapter,
        reasoning_log  = reasoning_log,
        price_feed     = price_feed,
        news_feed      = news_feed,
        scheduler      = scheduler,
        noise_pool     = noise_pool,
        event_loop     = loop,
    ))

    logger.info(f"Bots started: {[b.name for b in bot_list]}")
    logger.info(
        "Providers: "
        + ", ".join(f"{bot.name}={bot.llm_provider}" for bot in bot_list)
    )
    logger.info(f"Noise traders: {noise_pool.trader_count}")
    logger.info("API ready at http://localhost:8000")
    logger.info("Docs at      http://localhost:8000/docs")

    yield  # ← FastAPI serves requests here

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down scheduler…")
    scheduler.stop()
    logger.info("Shutdown complete")


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "AI Trading Arena",
    description = "5 LLM-powered bots trade real stocks in a C++ order book",
    version     = "3.0",
    lifespan    = lifespan,
)

setup_middleware(app)

app.include_router(bots.router,        prefix="/bots",    tags=["Bots"])
app.include_router(market.router,                         tags=["Market"])
app.include_router(leaderboard.router,                    tags=["Leaderboard"])
app.include_router(sandbox.router,     prefix="/sandbox", tags=["Sandbox"])
app.include_router(websocket.router,                      tags=["WebSocket"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Direct run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
