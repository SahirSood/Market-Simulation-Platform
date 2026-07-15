"""Phase D evaluation and replay endpoints."""
import asyncio
from fastapi import APIRouter, HTTPException, Query

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


@router.get("/evaluation/replay-runs/{run_id}")
async def get_replay_run(
    run_id: str,
    decision_limit: int = Query(500, ge=1, le=5000),
):
    """Replay run metadata plus aggregate metrics and recent decisions."""
    state = app_state.get()
    if state.replay_store is None:
        raise HTTPException(404, "Replay store is not configured")

    run = await asyncio.to_thread(state.replay_store.get_run, run_id)
    if not run:
        raise HTTPException(404, f"Replay run '{run_id}' not found")

    decisions = await asyncio.to_thread(
        state.replay_store.get_run_decisions,
        run_id,
        decision_limit,
    )
    summary = summarize_decisions(decisions)
    return {
        "run": run,
        "summary": summary,
        "provider_comparison": compare_model_groups(decisions, group_by="llm_provider"),
        "decisions": decisions,
        "decision_window": {
            "limit": decision_limit,
            "returned": len(decisions),
        },
    }


@router.get("/evaluation/replay-runs/{run_id}/decisions")
async def get_replay_run_decisions(
    run_id: str,
    limit: int = Query(500, ge=1, le=5000),
    bot_id: str | None = None,
):
    """Replay decisions for one run, optionally filtered to one bot."""
    state = app_state.get()
    if state.replay_store is None:
        raise HTTPException(404, "Replay store is not configured")

    run = await asyncio.to_thread(state.replay_store.get_run, run_id)
    if not run:
        raise HTTPException(404, f"Replay run '{run_id}' not found")

    return await asyncio.to_thread(
        state.replay_store.get_run_decisions,
        run_id,
        limit,
        bot_id,
    )
