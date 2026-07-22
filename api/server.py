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
import time
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
from liquidity      import seed_order_book_liquidity
from portfolio      import FillRecord
from reasoning_log  import ReasoningLog
from noise_traders  import NoiseTraderPool
from scheduler      import BotScheduler
from bots           import BearBot, DegenBot, AnalystBot, ContrarianBot, MacroBot
from rag.repository import RagRepository
from rag.embeddings import get_openai_embedding_service_from_env
from agent_tools    import MarketAgentToolServer
from risk           import RiskLimits
from research       import ResearchCoordinator
from replay         import ReplayStore
from audit          import AuditLog
from config import (
    DATABASE_URL,
    RAG_BOOTSTRAP_BOT_DELAY_SECS,
    RAG_BOOTSTRAP_EMBED_BATCH_SIZE,
    RAG_BOOTSTRAP_EMBED_LIMIT,
    RAG_BOOTSTRAP_FORMS,
    RAG_BOOTSTRAP_MAX_FILINGS,
    RAG_BOOTSTRAP_MAX_RETRIES,
    RAG_BOOTSTRAP_ON_STARTUP,
    RAG_BOOTSTRAP_TICKERS,
    RESEARCH_AUTO_INGEST_ENABLED,
)

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


def _restore_portfolios_from_reasoning_log(bot_list, reasoning_log) -> dict:
    """
    Hosted instances can restart while the Postgres decision log survives.
    Replaying exact fill rows keeps open positions and mark-to-market returns
    alive instead of resetting every bot to starting cash. Older databases fall
    back to summarized filled decision rows.
    """
    get_execution_fills = getattr(reasoning_log, "get_execution_fills", None)
    get_filled_decisions = getattr(reasoning_log, "get_filled_decisions", None)
    if not callable(get_execution_fills) and not callable(get_filled_decisions):
        return {"bots_restored": 0, "fills_replayed": 0}

    bots_restored = 0
    fills_replayed = 0
    for bot in bot_list:
        restored_for_bot = 0
        try:
            fill_rows = get_execution_fills(bot.bot_id) if callable(get_execution_fills) else []
        except Exception as exc:
            logger.warning("Execution-fill restore skipped for %s: %s", bot.bot_id, exc)
            fill_rows = []

        for row in fill_rows:
            ticker = row.get("ticker")
            side = str(row.get("side") or "").upper()
            quantity = row.get("quantity")
            price = row.get("price")
            if side not in {"BUY", "SELL"} or not ticker or not quantity or price is None:
                continue
            fill = FillRecord(
                order_id=int(row.get("engine_order_id") or row.get("execution_order_id") or row.get("id") or 0),
                ticker=str(ticker).upper(),
                side=side,
                quantity=int(quantity),
                price=float(price),
                timestamp=_timestamp_seconds(row.get("timestamp")),
            )
            bot.portfolio.apply_fill(fill, strict=False)
            restored_for_bot += 1

        if restored_for_bot:
            bots_restored += 1
            fills_replayed += restored_for_bot
            logger.info(
                "Restored %s portfolio from %s execution fill(s): %s",
                bot.bot_id,
                restored_for_bot,
                bot.portfolio.snapshot().get("positions", {}),
            )
            continue

        if not callable(get_filled_decisions):
            continue
        try:
            rows = get_filled_decisions(bot.bot_id)
        except Exception as exc:
            logger.warning("Decision-summary restore skipped for %s: %s", bot.bot_id, exc)
            continue

        for row in rows:
            action = str(row.get("action") or "").upper()
            ticker = row.get("ticker")
            quantity = row.get("fill_qty_total")
            price = row.get("fill_avg_price")
            if action not in {"BUY", "SELL"} or not ticker or not quantity or price is None:
                continue
            fill = FillRecord(
                order_id=int(row.get("id") or 0),
                ticker=str(ticker).upper(),
                side=action,
                quantity=int(quantity),
                price=float(price),
                timestamp=_timestamp_seconds(row.get("timestamp")),
            )
            bot.portfolio.apply_fill(fill, strict=False)
            restored_for_bot += 1

        if restored_for_bot:
            bots_restored += 1
            fills_replayed += restored_for_bot
            logger.info(
                "Restored %s portfolio from %s filled decision(s): %s",
                bot.bot_id,
                restored_for_bot,
                bot.portfolio.snapshot().get("positions", {}),
            )

    return {"bots_restored": bots_restored, "fills_replayed": fills_replayed}


def _timestamp_seconds(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    timestamp = getattr(value, "timestamp", None)
    if callable(timestamp):
        return float(timestamp())
    return time.time()

# ── API imports ───────────────────────────────────────────────────────────────
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
        RAG_BOOTSTRAP_ON_STARTUP
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

        tickers = [symbol.upper() for symbol in RAG_BOOTSTRAP_TICKERS]
        forms = [form.upper() for form in RAG_BOOTSTRAP_FORMS]
        max_filings = max(1, int(RAG_BOOTSTRAP_MAX_FILINGS))
        max_retries = max(0, int(RAG_BOOTSTRAP_MAX_RETRIES))
        embed_limit = max(1, int(RAG_BOOTSTRAP_EMBED_LIMIT))
        embed_batch_size = max(1, int(RAG_BOOTSTRAP_EMBED_BATCH_SIZE))
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
        logger.warning(
            "RAG bootstrap failed; API will continue without seeded evidence: %s",
            exc,
            exc_info=True,
        )


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
    seed_order_book_liquidity(price_feed, engine_adapter)
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
    initial_bot_delay_secs = RAG_BOOTSTRAP_BOT_DELAY_SECS if rag_bootstrap_thread is not None else 0.0
    research_coordinator = None
    if rag_repository is not None:
        research_coordinator = ResearchCoordinator(
            repository=rag_repository,
            db_url=getattr(rag_repository, "engine_url", None) or DATABASE_URL,
            embedding_service=embedding_service,
            price_feed=price_feed,
            engine_adapter=engine_adapter,
            enabled=RESEARCH_AUTO_INGEST_ENABLED,
        )
        research_coordinator.start()

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
    restore_summary = _restore_portfolios_from_reasoning_log(bot_list, reasoning_log)
    logger.info("Portfolio restore summary: %s", restore_summary)
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
        research_coordinator = research_coordinator,
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
        research_coordinator = research_coordinator,
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
    if research_coordinator is not None:
        research_coordinator.stop()
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
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "dashboard": os.getenv("FRONTEND_URL"),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Direct run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
