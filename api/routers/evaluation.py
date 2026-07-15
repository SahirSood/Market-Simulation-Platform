"""Phase D evaluation and replay endpoints."""
import asyncio
from fastapi import APIRouter, Query

from api import state as app_state
from evaluation import compare_model_groups, summarize_decisions

router = APIRouter()


@router.get("/evaluation/summary")
async def get_evaluation_summary(limit: int = Query(500, ge=1, le=5000)):
    """Evidence, speculation, citation, and provider comparison metrics."""
    state = app_state.get()
    rows = await asyncio.to_thread(
        state.reasoning_log.get_decisions,
        None,
        None,
        limit,
    )
    summary = summarize_decisions(rows)
    return {
        **summary,
        "provider_comparison": compare_model_groups(rows, group_by="llm_provider"),
        "decision_window": {
            "limit": limit,
            "returned": len(rows),
            "newest": rows[0]["timestamp"] if rows else None,
            "oldest": rows[-1]["timestamp"] if rows else None,
        },
    }


@router.get("/evaluation/replay-runs")
async def list_replay_runs(limit: int = Query(20, ge=1, le=100)):
    """Recent historical replay/model-comparison runs."""
    state = app_state.get()
    if state.replay_store is None:
        return []
    return await asyncio.to_thread(state.replay_store.list_runs, limit)
