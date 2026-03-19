"""POST /sandbox/start and POST /sandbox/stop"""
import sys
import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from api import state as app_state
from api.models import SandboxStatus
from api.dependencies import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

# Sandbox runs bots on a much faster 2-minute cycle for demo purposes
_SANDBOX_CYCLE_MINS = 2


@router.post("/start", response_model=SandboxStatus, dependencies=[Depends(verify_api_key)])
async def sandbox_start():
    """Start an isolated sandbox simulation with fresh bots and its own SQLite DB."""
    state = app_state.get()
    if state.sandbox_active:
        raise HTTPException(409, "Sandbox is already running")

    try:
        await asyncio.to_thread(_start_sandbox, state)
    except Exception as e:
        logger.error(f"[Sandbox] Failed to start: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to start sandbox: {e}")

    return SandboxStatus(active=True, message="Sandbox started")


@router.post("/stop", response_model=SandboxStatus, dependencies=[Depends(verify_api_key)])
async def sandbox_stop():
    """Stop the running sandbox."""
    state = app_state.get()
    if not state.sandbox_active:
        raise HTTPException(409, "Sandbox is not running")

    try:
        await asyncio.to_thread(_stop_sandbox, state)
    except Exception as e:
        logger.error(f"[Sandbox] Failed to stop: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to stop sandbox: {e}")

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
    from price_feed     import PriceFeed
    from engine_adapter import EngineAdapter
    from reasoning_log  import ReasoningLog
    from noise_traders  import NoiseTraderPool
    from scheduler      import BotScheduler
    from bots           import BearBot, DegenBot, AnalystBot, ContrarianBot, MacroBot
    import config as _config

    price_feed     = PriceFeed()
    engine_adapter = EngineAdapter()
    reasoning_log  = ReasoningLog(database_url="sqlite:///sandbox.db")

    bots = [
        BearBot(price_feed,       state.news_feed, "claude"),
        DegenBot(price_feed,      state.news_feed, "claude"),
        AnalystBot(price_feed,    state.news_feed, "claude"),
        ContrarianBot(price_feed, state.news_feed, "claude"),
        MacroBot(price_feed,      state.news_feed, "claude"),
    ]
    noise_pool = NoiseTraderPool(price_feed, engine_adapter, n_traders=5)

    # Temporarily override the cycle time for the sandbox scheduler
    original = _config.BOT_CYCLE_MINS
    _config.BOT_CYCLE_MINS = _SANDBOX_CYCLE_MINS

    scheduler = BotScheduler(bots, noise_pool, engine_adapter, reasoning_log)
    scheduler.start()

    _config.BOT_CYCLE_MINS = original  # restore global

    state.sandbox_scheduler = scheduler
    state.sandbox_active    = True
    logger.info("[Sandbox] Started with 5 bots, 2-min cycle")


def _stop_sandbox(state):
    if state.sandbox_scheduler:
        state.sandbox_scheduler.stop()
    state.sandbox_scheduler = None
    state.sandbox_active    = False
    logger.info("[Sandbox] Stopped")
