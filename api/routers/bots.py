"""GET /bots and GET /bots/{id}"""
import asyncio
from fastapi import APIRouter, HTTPException
from api import state as app_state
from api.models import BotSummary, BotDetail, PositionItem, DecisionSummary

try:
    from config import STARTING_CASH
except ImportError:  # pragma: no cover - direct router imports in tests/tools
    STARTING_CASH = 100_000.0

router = APIRouter()

_PERSONALITY_TAGS = {
    "BearBot":       "Pessimistic Bear",
    "DegenBot":      "Aggressive Degen",
    "AnalystBot":    "Methodical Analyst",
    "ContrarianBot": "Contrarian Fader",
    "MacroBot":      "Macro Trader",
}


def _base_name(bot) -> str:
    return getattr(bot, "base_name", bot.name.split(" (")[0])


def _tag(bot) -> str:
    base = _base_name(bot)
    return _PERSONALITY_TAGS.get(base, base)


async def _bot_summary(bot, state) -> BotSummary:
    snap = bot.portfolio.snapshot()

    # Blocking calls → thread pool
    total_value = await asyncio.to_thread(
        bot.portfolio.mark_to_market, state.price_feed
    )
    upnl_map = await asyncio.to_thread(
        bot.portfolio.unrealized_pnl, state.price_feed
    )
    unrealized = sum(upnl_map.values())
    realized   = bot.portfolio.realized_pnl()

    last_decisions = await asyncio.to_thread(
        state.reasoning_log.get_decisions, bot.bot_id, None, 1
    )
    last = last_decisions[0] if last_decisions else None

    return BotSummary(
        bot_id           = bot.bot_id,
        name             = bot.name,
        personality_tag  = _tag(bot),
        llm_provider     = bot.llm_provider,
        starting_cash    = float(STARTING_CASH),
        cash             = round(snap["cash"], 2),
        total_value      = round(total_value, 2),
        unrealized_pnl   = round(unrealized, 2),
        realized_pnl     = round(realized, 2),
        position_count   = len(snap["positions"]),
        last_action      = last["action"]    if last else None,
        last_ticker      = last["ticker"]    if last else None,
        last_decision_at = last["timestamp"] if last else None,
    )


@router.get("", response_model=list[BotSummary])
async def list_bots():
    """All live bot summaries with live portfolio values."""
    state = app_state.get()
    return await asyncio.gather(*[_bot_summary(bot, state) for bot in state.bots])


@router.get("/{bot_id}", response_model=BotDetail)
async def get_bot(bot_id: str):
    """Full detail for one bot: positions + recent 5 decisions."""
    state = app_state.get()
    bot = next((b for b in state.bots if b.bot_id == bot_id), None)
    if not bot:
        raise HTTPException(404, f"Bot '{bot_id}' not found")

    snap = bot.portfolio.snapshot()
    total_value = await asyncio.to_thread(bot.portfolio.mark_to_market, state.price_feed)
    upnl_map    = await asyncio.to_thread(bot.portfolio.unrealized_pnl, state.price_feed)
    realized    = bot.portfolio.realized_pnl()

    # Build position items
    positions = []
    for ticker, qty in snap["positions"].items():
        try:
            current_price = await asyncio.to_thread(state.price_feed.get_price, ticker)
        except Exception:
            current_price = snap["cost_basis"].get(ticker, 0.0)
        positions.append(PositionItem(
            ticker         = ticker,
            quantity       = qty,
            avg_cost       = round(snap["cost_basis"].get(ticker, 0.0), 4),
            current_price  = round(current_price, 2),
            unrealized_pnl = round(upnl_map.get(ticker, 0.0), 2),
        ))

    # Recent decisions
    raw_decisions = await asyncio.to_thread(
        state.reasoning_log.get_decisions, bot_id, None, 5
    )
    recent = [
        DecisionSummary(
            id             = d["id"],
            timestamp      = d["timestamp"],
            action         = d["action"],
            ticker         = d["ticker"],
            quantity       = d["quantity"],
            limit_price    = d["limit_price"],
            fill_count     = d["fill_count"],
            fill_qty_total = d["fill_qty_total"],
            fill_avg_price = d["fill_avg_price"],
            reasoning      = (d["reasoning"] or "")[:200],
            confidence     = d.get("confidence"),
            evidence_ids   = d.get("evidence_ids") or [],
            evidence_urls  = d.get("evidence_urls") or [],
            speculative    = bool(d.get("speculative", False)),
        )
        for d in raw_decisions
    ]

    return BotDetail(
        bot_id           = bot.bot_id,
        name             = bot.name,
        personality_tag  = _tag(bot),
        llm_provider     = bot.llm_provider,
        cash             = round(snap["cash"], 2),
        total_value      = round(total_value, 2),
        unrealized_pnl   = round(sum(upnl_map.values()), 2),
        realized_pnl     = round(realized, 2),
        positions        = positions,
        recent_decisions = recent,
    )
