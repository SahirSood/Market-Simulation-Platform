"""
WebSocket ConnectionManager — tracks connected clients and broadcasts events.

broadcast_from_thread() is the thread-safe entry point used by BotScheduler
daemon threads. It uses asyncio.run_coroutine_threadsafe to push into the
FastAPI event loop without blocking the scheduler thread.
"""
import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.add(ws)
        logger.info(f"[WS] Client connected — {len(self._active)} total")

    def disconnect(self, ws: WebSocket) -> None:
        self._active.discard(ws)
        logger.info(f"[WS] Client disconnected — {len(self._active)} remaining")

    async def broadcast(self, payload: dict) -> None:
        """Async broadcast — must be called from within the event loop."""
        if not self._active:
            return
        message = json.dumps(payload, default=str)
        dead: Set[WebSocket] = set()
        for ws in list(self._active):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._active -= dead

    def broadcast_from_thread(
        self, payload: dict, loop: asyncio.AbstractEventLoop
    ) -> None:
        """
        Thread-safe entry point — called from BotScheduler daemon threads.
        Uses run_coroutine_threadsafe so the broadcast coroutine runs in the
        FastAPI event loop, not in the scheduler thread.
        Windows-safe: no Unix pipes or signals involved.
        """
        if not self._active:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(payload), loop)


# Module-level singleton — imported by routers and server.py
manager = ConnectionManager()
