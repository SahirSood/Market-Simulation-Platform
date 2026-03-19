"""WebSocket /ws/live — real-time event stream."""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.ws_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    """
    Clients connect here to receive a real-time stream of:
      - {"type": "trade",    bot_id, bot_name, action, ticker, quantity, fill_count, timestamp}
      - {"type": "decision", bot_id, bot_name, action, ...} (includes HOLDs)
      - {"type": "heartbeat"} every 30s to keep the connection alive

    Events are pushed by BotScheduler via manager.broadcast_from_thread().
    """
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"[WS] Connection error: {e}")
        manager.disconnect(websocket)
