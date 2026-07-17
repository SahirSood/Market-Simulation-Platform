"""Phase D evaluation and replay endpoints."""
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query

from api import state as app_state
from evaluation import (
    compare_model_groups,
    compare_replay_runs,
    evaluate_retrieval_cases,
    get_bot_behavior_detail,
    list_risk_rejections,
    summarize_bot_behavior,
    summarize_decisions,
)

router = APIRouter()
RETRIEVAL_CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "retrieval_cases"


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


@router.get("/evaluation/bot-behavior")
async def get_bot_behavior(limit: int = Query(1000, ge=1, le=10000)):
    """Per-bot behavior analytics from live reasoning-log decisions."""
    state = app_state.get()
    rows = await asyncio.to_thread(
        state.reasoning_log.get_decisions,
        None,
        None,
        limit,
    )
    summary = summarize_bot_behavior(rows)
    return {
        **summary,
        "decision_window": {
            "limit": limit,
            "returned": len(rows),
            "newest": rows[0]["timestamp"] if rows else None,
            "oldest": rows[-1]["timestamp"] if rows else None,
        },
    }


@router.get("/evaluation/bot-behavior/{bot_id}")
async def get_bot_behavior_for_bot(
    bot_id: str,
    limit: int = Query(500, ge=1, le=5000),
):
    """Detailed behavior analytics and timeline for one bot."""
    state = app_state.get()
    rows = await asyncio.to_thread(
        state.reasoning_log.get_decisions,
        bot_id,
        None,
        limit,
    )
    if not rows:
        raise HTTPException(404, f"Bot '{bot_id}' has no logged decisions")
    detail = get_bot_behavior_detail(rows)
    return {
        **detail,
        "decision_window": {
            "limit": limit,
            "returned": len(rows),
            "newest": rows[0]["timestamp"] if rows else None,
            "oldest": rows[-1]["timestamp"] if rows else None,
        },
    }


@router.get("/evaluation/risk-rejections")
async def get_risk_rejections(
    limit: int = Query(100, ge=1, le=1000),
    decision_window: int = Query(2000, ge=1, le=10000),
):
    """Recent live decisions rejected by deterministic risk checks."""
    state = app_state.get()
    rows = await asyncio.to_thread(
        state.reasoning_log.get_decisions,
        None,
        None,
        decision_window,
    )
    return {
        **list_risk_rejections(rows, limit=limit),
        "decision_window": {
            "limit": decision_window,
            "returned": len(rows),
        },
    }


@router.get("/evaluation/evidence")
async def get_evidence_chunks(
    chunk_ids: str = Query(..., min_length=1),
    limit: int = Query(100, ge=1, le=500),
):
    """Fetch cited RAG chunks and filing metadata for evidence drilldown."""
    requested_ids = _parse_chunk_ids(chunk_ids)[:limit]
    if not requested_ids:
        raise HTTPException(400, "chunk_ids must include at least one integer id")

    state = app_state.get()
    repository = _get_rag_repository(state)
    if repository is None:
        raise HTTPException(404, "RAG repository is not configured")
    if not hasattr(repository, "get_chunks_by_ids"):
        raise HTTPException(501, "RAG repository does not support chunk lookup")

    chunks = await asyncio.to_thread(repository.get_chunks_by_ids, requested_ids)
    found_ids = {int(row["chunk_id"]) for row in chunks}
    return {
        "requested_ids": requested_ids,
        "chunks": chunks,
        "missing_ids": [chunk_id for chunk_id in requested_ids if chunk_id not in found_ids],
    }


@router.get("/evaluation/retrieval-summary")
async def get_retrieval_summary(
    case_file: str = "sec_basic_cases.json",
    top_k: int | None = Query(None, ge=1, le=50),
    use_embeddings: bool = False,
):
    """Run labeled retrieval cases against the configured RAG repository."""
    state = app_state.get()
    repository = _get_rag_repository(state)
    if repository is None:
        raise HTTPException(404, "RAG repository is not configured")

    metadata, cases = _load_retrieval_case_file(case_file)
    if top_k is not None:
        for case in cases:
            case["top_k"] = top_k
    embedding_service = getattr(state, "embedding_service", None) if use_embeddings else None
    result = await asyncio.to_thread(
        evaluate_retrieval_cases,
        repository,
        cases,
        embedding_service,
    )
    return {
        "metadata": metadata,
        "case_file": case_file,
        "embedding_enabled": bool(embedding_service),
        **result,
    }


@router.get("/evaluation/replay-runs")
async def list_replay_runs(limit: int = Query(20, ge=1, le=100)):
    """Recent historical replay/model-comparison runs."""
    state = app_state.get()
    if state.replay_store is None:
        return []
    return await asyncio.to_thread(state.replay_store.list_runs, limit)


@router.get("/evaluation/replay-runs/compare")
async def compare_replay_run_group(
    fingerprint: str | None = None,
    run_id: str | None = None,
    run_limit: int = Query(20, ge=1, le=100),
    decision_limit: int = Query(5000, ge=1, le=20000),
):
    """Compare replay runs that share the same input fingerprint."""
    state = app_state.get()
    if state.replay_store is None:
        raise HTTPException(404, "Replay store is not configured")

    selected_fingerprint = fingerprint
    if not selected_fingerprint and run_id:
        run = await asyncio.to_thread(state.replay_store.get_run, run_id)
        if not run:
            raise HTTPException(404, f"Replay run '{run_id}' not found")
        selected_fingerprint = run.get("input_fingerprint")
    if not selected_fingerprint:
        raise HTTPException(400, "fingerprint or run_id is required")

    runs = await asyncio.to_thread(
        state.replay_store.list_runs_by_input_fingerprint,
        selected_fingerprint,
        run_limit,
    )
    decisions_by_run = {}
    for run in runs:
        decisions_by_run[run["id"]] = await asyncio.to_thread(
            state.replay_store.get_run_decisions,
            run["id"],
            decision_limit,
        )

    return {
        **compare_replay_runs(runs, decisions_by_run),
        "decision_window": {
            "limit_per_run": decision_limit,
        },
    }


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


def _parse_chunk_ids(value: str) -> list[int]:
    ids = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    seen = set()
    deduped = []
    for chunk_id in ids:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduped.append(chunk_id)
    return deduped


def _get_rag_repository(state):
    repository = getattr(state, "rag_repository", None)
    if repository is not None:
        return repository
    for bot in getattr(state, "bots", []) or []:
        repository = getattr(bot, "rag_repository", None)
        if repository is not None:
            return repository
    return None


def _load_retrieval_case_file(case_file: str) -> tuple[dict, list[dict]]:
    requested = Path(case_file)
    if requested.name != case_file:
        raise HTTPException(400, "case_file must be a file in data/retrieval_cases")
    path = RETRIEVAL_CASES_DIR / requested.name
    try:
        resolved = path.resolve()
        root = RETRIEVAL_CASES_DIR.resolve()
        if root not in resolved.parents and resolved != root:
            raise HTTPException(400, "case_file must stay under data/retrieval_cases")
        with resolved.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        raise HTTPException(404, f"Retrieval case file '{case_file}' not found")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Retrieval case file is invalid JSON: {exc}")

    if isinstance(payload, list):
        return {}, payload
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise HTTPException(400, "Retrieval case file must be a list or object with cases")
    return {key: value for key, value in payload.items() if key != "cases"}, payload["cases"]
