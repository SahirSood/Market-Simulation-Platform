"""POST /sandbox/start and POST /sandbox/stop"""
import asyncio
import logging
import random
from fastapi import APIRouter, HTTPException, Depends
from api import state as app_state
from api.audit import record_audit_event
from api.dependencies import WritePrincipal, require_write_auth
from api.models import SandboxStatus

router = APIRouter()
logger = logging.getLogger(__name__)

# Sandbox runs bots on a much faster 2-minute cycle for demo purposes
_SANDBOX_CYCLE_MINS = 2
_SANDBOX_NOISE_INTERVAL = 5


class _SandboxNewsFeed:
    """Sandbox runs without real-news dependency."""

    def get_trending(self):
        return []

    def get_recent(self):
        return []

    def get_latest(self, ticker: str, n: int = 5):
        return []


class _SandboxPriceFeed:
    """
    Lightweight synthetic price feed for sandbox mode.
    Prices drift via a small random walk so bots and noise traders can run
    without any external market-data dependency.
    """

    _SEEDS = {
        "AAPL": 190.0,
        "NVDA": 490.0,
        "MSFT": 420.0,
        "GOOGL": 175.0,
        "TSLA": 180.0,
        "SPY": 510.0,
        "QQQ": 440.0,
        "TLT": 95.0,
        "GLD": 215.0,
        "IEF": 94.0,
    }

    def __init__(self):
        self._prices = dict(self._SEEDS)
        self._prev_close = dict(self._SEEDS)

    def _tick(self, ticker: str) -> float:
        current = self._prices.get(ticker, 100.0)
        move_pct = random.uniform(-0.005, 0.005)
        updated = max(1.0, round(current * (1 + move_pct), 2))
        self._prices[ticker] = updated
        return updated

    def get_price(self, ticker: str) -> float:
        symbol = ticker.upper().strip()
        return self._tick(symbol)

    def get_ohlcv(self, ticker: str) -> dict:
        symbol = ticker.upper().strip()
        current = self._tick(symbol)
        prev_close = self._prev_close.get(symbol, current)
        high = round(max(current, prev_close) * 1.002, 2)
        low = round(min(current, prev_close) * 0.998, 2)
        return {
            "open": prev_close,
            "high": high,
            "low": low,
            "close": prev_close,
            "volume": 1_000_000,
        }

    def get_active_tickers(self) -> list[str]:
        return list(self._prices.keys())


@router.post("/start", response_model=SandboxStatus)
async def sandbox_start(principal: WritePrincipal = Depends(require_write_auth)):
    """Start an isolated sandbox simulation with fresh bots and its own SQLite DB."""
    state = app_state.get()
    if state.sandbox_active:
        record_audit_event(
            state,
            principal,
            "sandbox.start",
            target_type="sandbox",
            status="failed",
            error="Sandbox is already running",
        )
        raise HTTPException(409, "Sandbox is already running")

    try:
        await asyncio.to_thread(_start_sandbox, state)
    except Exception as e:
        record_audit_event(
            state,
            principal,
            "sandbox.start",
            target_type="sandbox",
            status="failed",
            error=str(e),
        )
        logger.error(f"[Sandbox] Failed to start: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to start sandbox: {e}")

    record_audit_event(
        state,
        principal,
        "sandbox.start",
        target_type="sandbox",
        metadata={
            "bot_count": 5,
            "cycle_minutes": _SANDBOX_CYCLE_MINS,
            "noise_interval_seconds": _SANDBOX_NOISE_INTERVAL,
        },
    )
    return SandboxStatus(active=True, message="Sandbox started")


@router.post("/stop", response_model=SandboxStatus)
async def sandbox_stop(principal: WritePrincipal = Depends(require_write_auth)):
    """Stop the running sandbox."""
    state = app_state.get()
    if not state.sandbox_active:
        record_audit_event(
            state,
            principal,
            "sandbox.stop",
            target_type="sandbox",
            status="failed",
            error="Sandbox is not running",
        )
        raise HTTPException(409, "Sandbox is not running")

    try:
        await asyncio.to_thread(_stop_sandbox, state)
    except Exception as e:
        record_audit_event(
            state,
            principal,
            "sandbox.stop",
            target_type="sandbox",
            status="failed",
            error=str(e),
        )
        logger.error(f"[Sandbox] Failed to stop: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to stop sandbox: {e}")

    record_audit_event(state, principal, "sandbox.stop", target_type="sandbox")
    return SandboxStatus(active=False, message="Sandbox stopped")


@router.get("/status", response_model=SandboxStatus)
async def sandbox_status():
    state = app_state.get()
    return SandboxStatus(
        active  = state.sandbox_active,
        message = "Sandbox is running" if state.sandbox_active else "Sandbox is stopped",
    )


# ── Synchronous helpers (run via asyncio.to_thread) ───────────────────────────

def _start_sandbox(state):
    # Import simulator modules (path already set up by server.py)
    from engine_adapter import EngineAdapter
    from reasoning_log  import ReasoningLog
    from noise_traders  import NoiseTraderPool
    from scheduler      import BotScheduler
    from bots           import BearBot, DegenBot, AnalystBot, ContrarianBot, MacroBot

    price_feed     = _SandboxPriceFeed()
    engine_adapter = EngineAdapter()
    reasoning_log  = ReasoningLog(database_url="sqlite:///sandbox.db")
    news_feed      = _SandboxNewsFeed()

    bots = [
        BearBot(price_feed,       news_feed, "claude"),
        DegenBot(price_feed,      news_feed, "claude"),
        AnalystBot(price_feed,    news_feed, "claude"),
        ContrarianBot(price_feed, news_feed, "claude"),
        MacroBot(price_feed,      news_feed, "claude"),
    ]
    noise_pool = NoiseTraderPool(price_feed, engine_adapter, n_traders=5)

    scheduler = BotScheduler(
        bots,
        noise_pool,
        engine_adapter,
        reasoning_log,
        bot_cycle_mins=_SANDBOX_CYCLE_MINS,
        noise_interval_secs=_SANDBOX_NOISE_INTERVAL,
    )
    scheduler.start()

    state.sandbox_scheduler = scheduler
    state.sandbox_active    = True
    logger.info(
        "[Sandbox] Started with 5 bots, 2-min cycle, 5-second noise interval"
    )


def _stop_sandbox(state):
    if state.sandbox_scheduler:
        state.sandbox_scheduler.stop()
    state.sandbox_scheduler = None
    state.sandbox_active    = False
    logger.info("[Sandbox] Stopped")
