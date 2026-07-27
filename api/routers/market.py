"""GET /orderbook and GET /trades"""
import asyncio
from fastapi import APIRouter
from api import state as app_state
from api.models import OrderBookSnapshot, OrderLevel, TradeRecord

router = APIRouter()


def _snapshot_to_model(ticker: str, snapshot, trade_count: int) -> OrderBookSnapshot:
    """Convert a C++ pybind11 BookSnapshot to an OrderBookSnapshot Pydantic model."""
    bids = [OrderLevel(
                price=lvl.price,
                quantity=int(lvl.total_quantity),
                order_count=int(getattr(lvl, "order_count", 0) or 0),
            )
            for lvl in (snapshot.bids if snapshot else [])]
    asks = [OrderLevel(
                price=lvl.price,
                quantity=int(lvl.total_quantity),
                order_count=int(getattr(lvl, "order_count", 0) or 0),
            )
            for lvl in (snapshot.asks if snapshot else [])]
    spread    = snapshot.spread    if snapshot else None
    mid_price = snapshot.mid_price if snapshot else None
    return OrderBookSnapshot(
        ticker      = ticker,
        bids        = bids,
        asks        = asks,
        spread      = round(spread, 4)    if spread    else None,
        mid_price   = round(mid_price, 4) if mid_price else None,
        trade_count = trade_count,
    )


@router.get("/orderbook", response_model=list[OrderBookSnapshot])
async def get_orderbook():
    """Current order book snapshot for all active tickers."""
    state    = app_state.get()
    tickers  = state.price_feed.get_active_tickers()
    if not tickers:
        return []

    results = []
    for ticker in tickers:
        # Serialise engine calls — the engine adapter has a single lock
        snapshot    = await asyncio.to_thread(state.engine_adapter.get_snapshot, ticker)
        trade_count = await asyncio.to_thread(state.engine_adapter.get_trade_count, ticker)
        results.append(_snapshot_to_model(ticker, snapshot, trade_count))
    return results


@router.get("/trades", response_model=list[TradeRecord])
async def get_trades():
    """Most recent 50 bot execution records that resulted in fills."""
    state = app_state.get()
    get_execution_orders = getattr(state.reasoning_log, "get_execution_orders", None)
    rows = []
    if callable(get_execution_orders):
        rows = await asyncio.to_thread(get_execution_orders, None, None, 50, True)
    if not rows:
        rows = await asyncio.to_thread(state.reasoning_log.get_decisions, None, None, 50)
        rows = [row for row in rows if int(row.get("fill_qty_total") or 0) > 0]
    return [
        TradeRecord(
            id             = d["id"],
            timestamp      = d["timestamp"],
            bot_id         = d["bot_id"],
            bot_name       = d["bot_name"],
            action         = d["action"],
            ticker         = d["ticker"],
            quantity       = d["quantity"],
            fill_avg_price = d["fill_avg_price"],
            fill_qty_total = d["fill_qty_total"],
            reasoning      = (d["reasoning"] or "")[:200],
        )
        for d in rows
    ]
