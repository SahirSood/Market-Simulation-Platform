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
import threading
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
from rag.repository import RagRepository
from rag.embeddings import get_openai_embedding_service_from_env
from agent_tools    import MarketAgentToolServer
from risk           import RiskLimits
from replay         import ReplayStore
from audit          import AuditLog
from config import DATABASE_URL

_BOT_CLASSES = [
    BearBot,
    DegenBot,
    AnalystBot,
    ContrarianBot,
    MacroBot,
]
_LIVE_PROVIDERS = ["claude", "openai"]


def _offline_mode_enabled() -> bool:
    return os.getenv("ARENA_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}


def _required_env_vars(offline_mode: bool) -> list[str]:
    # Provider keys are optional at boot. Missing LLM clients already fall back
    # to HOLD decisions, keeping demo deploys healthy while accounts are set up.
    return ["DATABASE_URL"]


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


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using %s", name, raw, default)
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r; using %s", name, raw, default)
        return default


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return list(default)
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return values or list(default)


def _repository_document_count(rag_repository) -> int:
    if rag_repository is None:
        return 0
    count_documents = getattr(rag_repository, "count_documents", None)
    if not callable(count_documents):
        return 0
    try:
        return int(count_documents())
    except Exception as exc:
        logger.warning("RAG document count failed: %s", exc)
        return 0


def _rag_bootstrap_needed(rag_repository) -> bool:
    return (
        _bool_env("RAG_BOOTSTRAP_ON_STARTUP", default=False)
        and rag_repository is not None
        and _repository_document_count(rag_repository) == 0
    )


def _start_rag_bootstrap_if_needed(rag_repository, embedding_service):
    if not _rag_bootstrap_needed(rag_repository):
        return None

    thread = threading.Thread(
        target=_run_rag_bootstrap,
        args=(rag_repository, embedding_service),
        name="rag-bootstrap",
        daemon=True,
    )
    thread.start()
    return thread


def _run_rag_bootstrap(rag_repository, embedding_service) -> None:
    """Best-effort first-deploy seed so live demos have SEC evidence to retrieve."""
    try:
        from scripts.ingest_poller import poll_and_ingest_once
        from scripts.embed_worker import embed_once

        tickers = [symbol.upper() for symbol in _csv_env(
            "RAG_BOOTSTRAP_TICKERS",
            ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"],
        )]
        forms = [form.upper() for form in _csv_env("RAG_BOOTSTRAP_FORMS", ["10-K", "10-Q", "8-K"])]
        max_filings = max(1, _int_env("RAG_BOOTSTRAP_MAX_FILINGS", 1))
        max_retries = max(0, _int_env("RAG_BOOTSTRAP_MAX_RETRIES", 1))
        embed_limit = max(1, _int_env("RAG_BOOTSTRAP_EMBED_LIMIT", 1500))
        embed_batch_size = max(1, _int_env("RAG_BOOTSTRAP_EMBED_BATCH_SIZE", 64))
        db_url = getattr(rag_repository, "engine_url", None) or DATABASE_URL

        logger.info(
            "RAG bootstrap starting: tickers=%s forms=%s max_filings=%s",
            tickers,
            forms,
            max_filings,
        )
        ingest_result = poll_and_ingest_once(
            tickers=tickers,
            db_url=db_url,
            max_filings=max_filings,
            forms=forms,
            repository=rag_repository,
            ingestion_service=None,
            max_retries=max_retries,
        )
        embedded = embed_once(
            db_url=db_url,
            limit=embed_limit,
            batch_size=embed_batch_size,
            repository=rag_repository,
            embedding_service=embedding_service,
            max_retries=max_retries,
        )
        logger.info(
            "RAG bootstrap complete: updated_tickers=%s embedded=%s documents=%s chunks=%s",
            ingest_result.get("updated_tickers", []),
            embedded,
            rag_repository.count_documents(),
            rag_repository.count_chunks(),
        )
    except Exception as exc:
        logger.warning("RAG bootstrap failed; API will continue without seeded evidence: %s", exc, exc_info=True)

# ── API imports ───────────────────────────────────────────────────────────────
from fastapi import FastAPI
from api import state as app_state
from api.ws_manager import manager as ws_manager
from api.middleware import setup_middleware
from api.routers import audit, bots, market, leaderboard, sandbox, websocket, evaluation, config, ops, mcp


# ── Lifespan (startup + shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Validate required env vars ────────────────────────────────────────────
    offline_mode = _offline_mode_enabled()
    required = _required_env_vars(offline_mode)
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
    risk_limits = RiskLimits()
    replay_store = ReplayStore(DATABASE_URL)
    audit_log = AuditLog(DATABASE_URL)
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
    rag_bootstrap_thread = _start_rag_bootstrap_if_needed(rag_repository, embedding_service)
    initial_bot_delay_secs = (
        _float_env("RAG_BOOTSTRAP_BOT_DELAY_SECS", 120.0)
        if rag_bootstrap_thread is not None
        else 0.0
    )

    bot_list = []
    for provider in _LIVE_PROVIDERS:
        for bot_cls in _BOT_CLASSES:
            bot_list.append(_make_bot(
                bot_cls,
                price_feed,
                news_feed,
                provider,
                rag_repository=rag_repository,
                embedding_service=embedding_service,
                agent_tool_server=agent_tool_server,
            ))
    agent_tool_server.set_bots(bot_list)
    noise_pool = NoiseTraderPool(price_feed, engine_adapter, n_traders=0 if offline_mode else 10)

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
        risk_limits    = risk_limits,
        initial_bot_delay_secs = initial_bot_delay_secs,
    )
    if not offline_mode:
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
        replay_store    = replay_store,
        rag_repository  = rag_repository,
        embedding_service = embedding_service,
        risk_limits     = risk_limits,
        agent_tool_server = agent_tool_server,
        audit_log       = audit_log,
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
    description = "10 LLM-powered bots trade real stocks in a C++ order book",
    version     = "3.0",
    lifespan    = lifespan,
)

setup_middleware(app)

app.include_router(bots.router,        prefix="/bots",    tags=["Bots"])
app.include_router(market.router,                         tags=["Market"])
app.include_router(leaderboard.router,                    tags=["Leaderboard"])
app.include_router(evaluation.router,                     tags=["Evaluation"])
app.include_router(config.router,                         tags=["Config"])
app.include_router(ops.router,                            tags=["Ops"])
app.include_router(mcp.router,                            tags=["MCP"])
app.include_router(audit.router,                          tags=["Audit"])
app.include_router(sandbox.router,     prefix="/sandbox", tags=["Sandbox"])
app.include_router(websocket.router,                      tags=["WebSocket"])


@app.get("/")
async def root():
    return {
        "name": "AI Trading Arena API",
        "status": "ok",
        "dashboard": os.getenv("FRONTEND_URL"),
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Direct run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
