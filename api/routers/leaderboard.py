"""GET /leaderboard and GET /bot/{id}/reasoning"""
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from api import state as app_state
from api.models import LeaderboardEntry, ReasoningEntry

router = APIRouter()

_PERSONALITY_TAGS = {
    "BearBot":       "Pessimistic Bear",
    "DegenBot":      "Aggressive Degen",
    "AnalystBot":    "Methodical Analyst",
    "ContrarianBot": "Contrarian Fader",
    "MacroBot":      "Macro Trader",
}

try:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "simulator"))
    from config import STARTING_CASH
except ImportError:
    STARTING_CASH = 100_000


def _snapshot_total_value(snapshot: dict | None) -> float:
    """
    Recover a comparable portfolio value from a stored snapshot.
    Prefer the persisted mark-to-market total when present; otherwise fall back
    to cash plus position value at stored cost basis.
    """
    if not snapshot:
        return float(STARTING_CASH)

    total_value = snapshot.get("total_value")
    if total_value is not None:
        return float(total_value)

    cash = float(snapshot.get("cash", STARTING_CASH))
    positions = snapshot.get("positions", {}) or {}
    cost_basis = snapshot.get("cost_basis", {}) or {}
    inventory_value = sum(
        float(cost_basis.get(ticker, 0.0)) * quantity
        for ticker, quantity in positions.items()
    )
    return cash + inventory_value


def _base_name(bot) -> str:
    return getattr(bot, "base_name", bot.name.split(" (")[0])


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard():
    """5 bots ranked by today's P&L (descending)."""
    state = app_state.get()
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    entries = []
    for bot in state.bots:
        total_value = await asyncio.to_thread(bot.portfolio.mark_to_market, state.price_feed)
        alltime_pnl = total_value - STARTING_CASH

        # Today's P&L: compare current value to portfolio snapshot at start of today
        today_decisions = await asyncio.to_thread(
            state.reasoning_log.get_decisions, bot.bot_id, None, 200, today_start
        )
        trade_count_today = len([d for d in today_decisions if d["action"] != "HOLD"])

        baseline_value = float(STARTING_CASH)
        if today_decisions:
            # Earliest decision today is last in the list because rows are newest-first.
            baseline_value = _snapshot_total_value(
                today_decisions[-1].get("portfolio_snapshot")
            )
        else:
            pre_today = await asyncio.to_thread(
                state.reasoning_log.get_decisions,
                bot.bot_id,
                None,
                1,
                None,
                today_start,
            )
            if pre_today:
                baseline_value = _snapshot_total_value(
                    pre_today[0].get("portfolio_snapshot")
                )

        today_pnl = total_value - baseline_value

        entries.append({
            "bot":              bot,
            "total_value":      total_value,
            "alltime_pnl":      alltime_pnl,
            "today_pnl":        today_pnl,
            "trade_count_today": trade_count_today,
        })

    # Sort by today's P&L descending, assign ranks
    entries.sort(key=lambda e: e["today_pnl"], reverse=True)
    return [
        LeaderboardEntry(
            rank              = i + 1,
            bot_id            = e["bot"].bot_id,
            name              = e["bot"].name,
            personality_tag   = _PERSONALITY_TAGS.get(
                _base_name(e["bot"]), _base_name(e["bot"])
            ),
            today_pnl         = round(e["today_pnl"], 2),
            alltime_pnl       = round(e["alltime_pnl"], 2),
            total_value       = round(e["total_value"], 2),
            trade_count_today = e["trade_count_today"],
        )
        for i, e in enumerate(entries)
    ]


@router.get("/bot/{bot_id}/reasoning", response_model=list[ReasoningEntry])
async def get_reasoning(bot_id: str):
    """Last 20 decisions for one bot with full reasoning text."""
    state = app_state.get()
    bot = next((b for b in state.bots if b.bot_id == bot_id), None)
    if not bot:
        raise HTTPException(404, f"Bot '{bot_id}' not found")

    rows = await asyncio.to_thread(state.reasoning_log.get_decisions, bot_id, None, 20)
    return [
        ReasoningEntry(
            id                 = d["id"],
            timestamp          = d["timestamp"],
            action             = d["action"],
            ticker             = d["ticker"],
            quantity           = d["quantity"],
            limit_price        = d["limit_price"],
            reasoning          = d["reasoning"] or "",
            headline_used      = d["headline_used"],
            fill_count         = d["fill_count"],
            fill_qty_total     = d["fill_qty_total"],
            fill_avg_price     = d["fill_avg_price"],
            portfolio_snapshot = d["portfolio_snapshot"] or {},
        )
        for d in rows
    ]
