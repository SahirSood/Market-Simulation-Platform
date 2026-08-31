"""Phase D evaluation and replay endpoints."""
import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api import state as app_state
from api.audit import record_audit_event
from api.dependencies import WritePrincipal, require_write_auth
from config import (
    BENCHMARK_TICKERS,
    DATABASE_URL,
    LIVE_EVALUATION_REPORT_DECISION_LIMIT,
    LIVE_EVALUATION_REPORT_LOOKBACK_DAYS,
    LIVE_EVALUATION_REPORT_MIN_SAMPLES,
    TRADABLE_TICKERS,
)
from evaluation import (
    compare_model_groups,
    compare_replay_runs,
    evaluate_retrieval_cases,
    get_bot_behavior_detail,
    list_risk_rejections,
    summarize_bot_behavior,
    summarize_decisions,
)
from outcomes import OUTCOME_HORIZONS, evaluate_due_outcomes, summarize_outcomes
from live_evaluation import generate_live_evaluation_report
from replay_workflow import (
    DEFAULT_BOTS,
    DEFAULT_PROVIDERS,
    REPLAY_EVENTS_DIR,
    load_replay_event_file,
    run_historical_replay,
    validate_replay_events,
)

router = APIRouter()
RETRIEVAL_CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "retrieval_cases"
RETRIEVAL_HISTORY_PATH = Path(__file__).resolve().parents[2] / "data" / "retrieval_runs" / "history.jsonl"
REPLAY_RESEARCH_REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "ml" / "reports"
REPLAY_RESEARCH_DATASET_DIR = Path(__file__).resolve().parents[2] / "data" / "ml" / "datasets"
PREFERRED_REPLAY_EVENT_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "replay_events"
    / "generated"
    / "six_month_daily_backfilled_large_cap_2026-02-18_2026-08-18.json"
)
BRIEF_SECTORS = {
    "ai_infrastructure": {
        "label": "AI Infrastructure / Large-Cap Technology",
        "tickers": list(TRADABLE_TICKERS),
        "benchmarks": list(BENCHMARK_TICKERS),
    }
}


class ReplayRunCreateRequest(BaseModel):
    name: str | None = None
    event_file: str | None = None
    events: list[dict] | None = None
    providers: list[str] = Field(default_factory=lambda: list(DEFAULT_PROVIDERS))
    bots: list[str] = Field(default_factory=lambda: list(DEFAULT_BOTS))
    execute_orders: bool = False
    notes: str | None = None
    config: dict = Field(default_factory=dict)


class OutcomeUpdateRequest(BaseModel):
    horizons: list[str] | None = None
    decision_limit: int = Field(default=1000, ge=1, le=10000)


@router.get("/evaluation/decision-brief")
async def get_decision_brief(
    ticker: str = Query("NVDA", min_length=1, max_length=16),
    sector: str = Query("ai_infrastructure", pattern=r"^[A-Za-z0-9_-]+$"),
    include_evidence: bool = Query(True),
):
    """Focused market recap and benchmark context for the tech trading arena."""
    return await asyncio.to_thread(_build_decision_brief, ticker, sector, include_evidence)


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


@router.get("/evaluation/live-report")
async def get_live_evaluation_report(
    period_days: int = Query(LIVE_EVALUATION_REPORT_LOOKBACK_DAYS, ge=1, le=90),
    min_samples: int = Query(LIVE_EVALUATION_REPORT_MIN_SAMPLES, ge=1, le=10000),
    horizon: str = Query("1d", pattern="^(immediate|1h|6h|1d|7d|all)$"),
    limit: int = Query(LIVE_EVALUATION_REPORT_DECISION_LIMIT, ge=1, le=50000),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
):
    """Return the no-LLM live report for the focused trading universe."""
    state = app_state.get()
    try:
        return await asyncio.to_thread(
            generate_live_evaluation_report,
            state.reasoning_log,
            period_days=period_days,
            min_samples=min_samples,
            decision_limit=limit,
            horizon=horizon,
            since=since,
            until=until,
            universe=TRADABLE_TICKERS,
            benchmarks=BENCHMARK_TICKERS,
            include_markdown=True,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/evaluation/outcomes/summary")
async def get_outcome_summary(
    horizon: str = Query("1h", pattern="^(immediate|1h|6h|1d|7d|all)$"),
    limit: int = Query(2000, ge=1, le=10000),
):
    """Outcome labels and PnL/cost metrics for live decisions."""
    state = app_state.get()
    getter = getattr(state.reasoning_log, "get_decision_outcomes", None)
    if not callable(getter):
        rows = []
    else:
        rows = await asyncio.to_thread(
            getter,
            None,
            None if horizon == "all" else horizon,
            None,
            limit,
        )
    return {
        **summarize_outcomes(rows),
        "outcome_window": {
            "horizon": horizon,
            "limit": limit,
            "returned": len(rows),
            "newest": rows[0]["observed_at"] if rows else None,
            "oldest": rows[-1]["observed_at"] if rows else None,
        },
        "available_horizons": ["immediate", *OUTCOME_HORIZONS.keys()],
    }


@router.get("/evaluation/outcomes/recent")
async def get_recent_outcomes(
    horizon: str = Query("1h", pattern="^(immediate|1h|6h|1d|7d|all)$"),
    status: str | None = Query(None, max_length=32),
    bot_id: str | None = Query(None, max_length=64),
    limit: int = Query(100, ge=1, le=1000),
):
    """Recent persisted outcome rows for drilldown and export."""
    state = app_state.get()
    getter = getattr(state.reasoning_log, "get_decision_outcomes", None)
    if not callable(getter):
        rows = []
    else:
        rows = await asyncio.to_thread(
            getter,
            bot_id,
            None if horizon == "all" else horizon,
            status,
            limit,
        )
    return {
        "outcomes": rows,
        "limit": limit,
        "returned": len(rows),
        "filters": {
            "horizon": horizon,
            "status": status,
            "bot_id": bot_id,
        },
    }


@router.post("/evaluation/outcomes/update")
async def update_decision_outcomes(
    request: OutcomeUpdateRequest,
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Create due horizon outcome labels for live decisions."""
    state = app_state.get()
    try:
        getter = getattr(state.reasoning_log, "get_decision_outcomes", None)
        writer = getattr(state.reasoning_log, "record_decision_outcome", None)
        if not callable(getter) or not callable(writer):
            raise HTTPException(501, "Reasoning log does not support outcome labels")
        result = await asyncio.to_thread(
            evaluate_due_outcomes,
            state.reasoning_log,
            state.price_feed,
            horizons=request.horizons,
            decision_limit=request.decision_limit,
        )
        record_audit_event(
            state,
            principal,
            "decision_outcomes.update",
            target_type="decision_outcomes",
            metadata={
                "horizons": request.horizons,
                "decision_limit": request.decision_limit,
                "created_count": result["created_count"],
            },
        )
        return result
    except HTTPException as exc:
        record_audit_event(
            state,
            principal,
            "decision_outcomes.update",
            target_type="decision_outcomes",
            status="failed",
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        record_audit_event(
            state,
            principal,
            "decision_outcomes.update",
            target_type="decision_outcomes",
            status="failed",
            error=str(exc),
        )
        raise HTTPException(500, f"Outcome update failed: {exc}")


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


@router.get("/evaluation/agent-activity")
async def get_agent_activity(
    bot_id: str | None = None,
    event_type: str | None = Query(None, pattern="^[a-zA-Z_]+$"),
    stage: str | None = Query(None, max_length=64),
    limit: int = Query(150, ge=1, le=1000),
):
    """Recent public-safe agent activity: model, RAG, tool, risk, and execution stages."""
    state = app_state.get()
    getter = getattr(state.reasoning_log, "get_agent_activity", None)
    if not callable(getter):
        return {"activity": [], "limit": limit, "returned": 0}
    rows = await asyncio.to_thread(
        getter,
        bot_id,
        limit,
        event_type,
        stage,
    )
    return {
        "activity": rows,
        "limit": limit,
        "returned": len(rows),
        "filters": {
            "bot_id": bot_id,
            "event_type": event_type,
            "stage": stage,
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


@router.get("/evaluation/retrieval-history")
async def get_retrieval_history(limit: int = Query(20, ge=1, le=200)):
    """Recent retrieval benchmark runs recorded by scripts/eval_retrieval.py."""
    return {
        "history": _load_retrieval_history(limit),
        "path": str(RETRIEVAL_HISTORY_PATH),
    }


@router.get("/evaluation/replay-fixtures")
async def list_replay_fixtures():
    """Bundled replay scenarios available for no-lookahead evaluation runs."""
    return await asyncio.to_thread(_load_replay_fixtures)


@router.get("/evaluation/replay-research")
async def get_replay_research(
    version: str = Query("v2", pattern=r"^[A-Za-z0-9_.-]+$"),
):
    """Latest replay research standings, model-suite summary, and report text."""
    return await asyncio.to_thread(_load_replay_research, version)


@router.get("/evaluation/replay-runs")
async def list_replay_runs(limit: int = Query(20, ge=1, le=100)):
    """Recent historical replay/model-comparison runs."""
    state = app_state.get()
    if state.replay_store is None:
        return []
    return await asyncio.to_thread(state.replay_store.list_runs, limit)


@router.post("/evaluation/replay-runs")
async def create_replay_run(
    request: ReplayRunCreateRequest,
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Create and execute a protected isolated historical replay run."""
    state = app_state.get()

    try:
        if state.replay_store is None:
            raise HTTPException(404, "Replay store is not configured")
        file_name = None
        file_config = {}
        if request.events is not None:
            events = validate_replay_events(request.events)
        elif request.event_file:
            file_name, file_config, events = load_replay_event_file(request.event_file)
        else:
            raise ValueError("Provide either events or event_file")

        config = {
            **file_config,
            **(request.config or {}),
            "source": "api",
            "event_file": request.event_file,
        }
        name = request.name or file_name or request.event_file or "api replay"
        result = await asyncio.to_thread(
            run_historical_replay,
            database_url=getattr(state.replay_store, "database_url", None)
            or DATABASE_URL
            or "sqlite:///:memory:",
            events=events,
            name=name,
            config=config,
            providers=request.providers,
            bot_names=request.bots,
            execute_orders=request.execute_orders,
            notes=request.notes,
            replay_store=state.replay_store,
            rag_repository=_get_rag_repository(state),
        )
        record_audit_event(
            state,
            principal,
            "replay.run.create",
            target_type="replay_run",
            target_id=result["run_id"],
            metadata={
                "event_count": len(events),
                "event_file": request.event_file,
                "providers": request.providers,
                "bots": request.bots,
                "execute_orders": request.execute_orders,
            },
        )
        return result
    except ValueError as exc:
        record_audit_event(
            state,
            principal,
            "replay.run.create",
            target_type="replay_run",
            status="failed",
            metadata={
                "event_file": request.event_file,
                "providers": request.providers,
                "bots": request.bots,
                "execute_orders": request.execute_orders,
            },
            error=str(exc),
        )
        raise HTTPException(400, str(exc))
    except HTTPException as exc:
        record_audit_event(
            state,
            principal,
            "replay.run.create",
            target_type="replay_run",
            status="failed",
            metadata={
                "event_file": request.event_file,
                "providers": request.providers,
                "bots": request.bots,
                "execute_orders": request.execute_orders,
            },
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        record_audit_event(
            state,
            principal,
            "replay.run.create",
            target_type="replay_run",
            status="failed",
            metadata={
                "event_file": request.event_file,
                "providers": request.providers,
                "bots": request.bots,
                "execute_orders": request.execute_orders,
            },
            error=str(exc),
        )
        raise HTTPException(500, f"Replay run failed: {exc}")


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


def _load_retrieval_history(limit: int) -> list[dict]:
    if not RETRIEVAL_HISTORY_PATH.exists():
        return []
    rows = []
    with RETRIEVAL_HISTORY_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:][::-1]


def _build_decision_brief(ticker: str, sector: str, include_evidence: bool = True) -> dict:
    symbol = str(ticker or "").upper().strip()
    sector_config = _brief_sector_config(sector)
    if symbol not in sector_config["tickers"]:
        raise HTTPException(
            400,
            (
                f"Ticker '{symbol}' is outside the focused universe. "
                f"Choose one of: {', '.join(sector_config['tickers'])}."
            ),
        )

    state = app_state.get()
    current_prices = _brief_current_prices(state, [symbol, *sector_config["benchmarks"]])
    history = _load_replay_event_price_history([symbol, *sector_config["benchmarks"]])
    trends = _brief_trends(symbol, sector_config["benchmarks"], history)
    evidence = _brief_evidence(state, symbol) if include_evidence else []
    recent_decisions = _brief_recent_decisions(state, symbol)
    agent_views = _brief_agent_views(recent_decisions)
    replay_research = _load_replay_research("v2")
    replay_context = _brief_replay_context(symbol, replay_research)
    recommendation = _brief_recommendation(
        symbol=symbol,
        trends=trends,
        agent_views=agent_views,
        evidence=evidence,
        replay_context=replay_context,
    )

    return {
        "available": True,
        "evidence_included": include_evidence,
        "ticker": symbol,
        "sector": sector,
        "sector_label": sector_config["label"],
        "universe": {
            "tradable_tickers": sector_config["tickers"],
            "benchmark_tickers": sector_config["benchmarks"],
        },
        "so_what": recommendation["summary"],
        "recommendation": recommendation,
        "current_prices": current_prices,
        "what_changed": {
            "source": "historical_replay_events",
            "source_file": str(PREFERRED_REPLAY_EVENT_FILE),
            "as_of_time": trends.get("as_of_time"),
            "ticker": trends.get("ticker"),
            "benchmarks": trends.get("benchmarks") or [],
            "comparisons": trends.get("comparisons") or [],
            "normalized_series": trends.get("normalized_series") or [],
        },
        "why_it_matters": _brief_why_it_matters(symbol, trends, evidence, replay_context),
        "decision_options": _brief_decision_options(recommendation["category"]),
        "agent_debate": agent_views,
        "evidence": evidence,
        "benchmark_check": {
            "benchmarks": sector_config["benchmarks"],
            "comparisons": trends.get("comparisons") or [],
            "replay_context": replay_context,
        },
        "risk_view": _brief_risk_view(symbol, trends, agent_views, replay_context),
        "what_would_change_my_mind": _brief_change_triggers(symbol, recommendation["category"], trends),
        "caveats": _brief_caveats(replay_research, recent_decisions, evidence),
    }


def _brief_sector_config(sector: str) -> dict:
    key = str(sector or "ai_infrastructure").strip().lower()
    config = BRIEF_SECTORS.get(key)
    if not config:
        raise HTTPException(
            400,
            f"Unsupported sector '{sector}'. Supported sectors: {', '.join(sorted(BRIEF_SECTORS))}.",
        )
    return {
        "label": config["label"],
        "tickers": [str(t).upper() for t in config["tickers"]],
        "benchmarks": [str(t).upper() for t in config["benchmarks"]],
    }


def _brief_current_prices(state, tickers: list[str]) -> dict:
    rows = {}
    price_feed = getattr(state, "price_feed", None)
    getter = getattr(price_feed, "get_price", None)
    if not callable(getter):
        return rows
    for ticker in tickers:
        try:
            rows[ticker] = {"price": round(float(getter(ticker)), 4), "available": True}
        except Exception as exc:
            rows[ticker] = {"price": None, "available": False, "error": str(exc)[:160]}
    return rows


def _load_replay_event_price_history(tickers: list[str]) -> dict[str, list[dict]]:
    symbols = {str(t).upper().strip() for t in tickers if str(t).strip()}
    series = {ticker: [] for ticker in symbols}
    if not PREFERRED_REPLAY_EVENT_FILE.exists():
        return series
    try:
        payload = json.loads(PREFERRED_REPLAY_EVENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return series
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return series
    for event in events:
        if not isinstance(event, dict):
            continue
        timestamp = event.get("as_of_time") or event.get("timestamp")
        prices = event.get("prices") or {}
        if not isinstance(prices, dict):
            continue
        for ticker in symbols:
            value = _safe_number(prices.get(ticker))
            if value is not None:
                series[ticker].append({"timestamp": timestamp, "price": value})
    return series


def _brief_trends(symbol: str, benchmarks: list[str], history: dict[str, list[dict]]) -> dict:
    ticker_series = history.get(symbol) or []
    trend_rows = [
        _period_return(ticker_series, "1m", 21),
        _period_return(ticker_series, "3m", 63),
        _period_return(ticker_series, "6m", 126),
    ]
    benchmark_rows = []
    comparisons = []
    for benchmark in benchmarks:
        benchmark_series = history.get(benchmark) or []
        periods = [
            _period_return(benchmark_series, "1m", 21),
            _period_return(benchmark_series, "3m", 63),
            _period_return(benchmark_series, "6m", 126),
        ]
        benchmark_rows.append({"ticker": benchmark, "periods": periods})
        for ticker_period, benchmark_period in zip(trend_rows, periods):
            excess = None
            if ticker_period.get("return") is not None and benchmark_period.get("return") is not None:
                excess = round(ticker_period["return"] - benchmark_period["return"], 6)
            comparisons.append({
                "benchmark": benchmark,
                "period": ticker_period["period"],
                "ticker_return": ticker_period.get("return"),
                "benchmark_return": benchmark_period.get("return"),
                "excess_return": excess,
                "beat_benchmark": None if excess is None else excess > 0,
            })
    return {
        "as_of_time": ticker_series[-1]["timestamp"] if ticker_series else None,
        "ticker": {"ticker": symbol, "periods": trend_rows},
        "benchmarks": benchmark_rows,
        "comparisons": comparisons,
        "normalized_series": _normalized_return_series(history, [symbol, *benchmarks]),
    }


def _normalized_return_series(
    history: dict[str, list[dict]],
    tickers: list[str],
    max_points: int = 126,
) -> list[dict]:
    """Return a compact, chart-ready six-month series rebased to zero percent."""
    rows = []
    for ticker in tickers:
        source = (history.get(ticker) or [])[-max_points:]
        if not source:
            rows.append({"ticker": ticker, "points": []})
            continue
        base_price = _safe_number(source[0].get("price"))
        points = []
        for point in source:
            price = _safe_number(point.get("price"))
            normalized_return = None
            if base_price and price is not None:
                normalized_return = round((price - base_price) / base_price, 6)
            points.append({
                "timestamp": point.get("timestamp"),
                "price": price,
                "return": normalized_return,
            })
        rows.append({"ticker": ticker, "points": points})
    return rows


def _period_return(series: list[dict], label: str, trading_days: int) -> dict:
    if not series:
        return {
            "period": label,
            "available": False,
            "start_price": None,
            "end_price": None,
            "return": None,
        }
    end = series[-1]
    start_index = max(0, len(series) - trading_days - 1)
    start = series[start_index]
    start_price = _safe_number(start.get("price"))
    end_price = _safe_number(end.get("price"))
    value = None
    if start_price and end_price is not None:
        value = round((end_price - start_price) / start_price, 6)
    return {
        "period": label,
        "available": value is not None,
        "start_time": start.get("timestamp"),
        "end_time": end.get("timestamp"),
        "start_price": start_price,
        "end_price": end_price,
        "return": value,
    }


def _brief_evidence(state, symbol: str) -> list[dict]:
    repository = getattr(state, "rag_repository", None)
    retrieve = getattr(repository, "retrieve_evidence", None)
    if not callable(retrieve):
        return []
    query = (
        f"{symbol} AI infrastructure revenue margin data center capex guidance "
        "risk demand valuation"
    )
    try:
        rows = retrieve(
            ticker=symbol,
            query_text=query,
            top_k=5,
            # Keep the arena recap local and fast; the Research workbench owns
            # deeper embedding-backed retrieval and its external API latency.
            embedding_service=None,
        )
    except Exception:
        rows = []
    return [_brief_evidence_row(row) for row in rows or []]


def _brief_evidence_row(row: dict) -> dict:
    content = str(row.get("content") or "").strip().replace("\n", " ")
    if len(content) > 360:
        content = content[:360] + "..."
    return {
        "chunk_id": row.get("chunk_id"),
        "document_id": row.get("document_id"),
        "ticker": row.get("ticker"),
        "title": row.get("title") or row.get("source_name") or "Evidence item",
        "source_url": row.get("source_url"),
        "source_type": row.get("source_type"),
        "source_name": row.get("source_name"),
        "form_type": row.get("form_type"),
        "published_at": row.get("published_at"),
        "score": row.get("score"),
        "content": content,
    }


def _brief_recent_decisions(state, symbol: str) -> list[dict]:
    getter = getattr(getattr(state, "reasoning_log", None), "get_decisions", None)
    if not callable(getter):
        return []
    try:
        rows = getter(None, None, 500)
    except Exception:
        return []
    filtered = []
    for row in rows or []:
        ticker = str(row.get("ticker") or "").upper().strip()
        reasoning = str(row.get("reasoning") or "")
        if ticker == symbol or (not ticker and symbol in reasoning.upper()):
            filtered.append(row)
    return filtered


def _brief_agent_views(rows: list[dict]) -> list[dict]:
    bases = ["AnalystBot", "MacroBot", "BearBot"]
    by_key = {}
    for row in rows:
        base = _base_bot_name(row.get("bot_name"))
        if base not in bases:
            continue
        provider = str(row.get("llm_provider") or "unknown").lower()
        key = (base, provider)
        if key not in by_key:
            by_key[key] = {
                "perspective": base.replace("Bot", ""),
                "bot_name": row.get("bot_name"),
                "provider": provider,
                "action": row.get("action"),
                "ticker": row.get("ticker"),
                "confidence": row.get("confidence"),
                "reasoning": row.get("reasoning"),
                "headline_used": row.get("headline_used"),
                "timestamp": row.get("timestamp"),
                "evidence_ids": row.get("evidence_ids") or [],
                "hold_cause": row.get("hold_cause"),
                "status": "available",
            }
    views = list(by_key.values())
    existing = {row["perspective"] for row in views}
    for base in bases:
        label = base.replace("Bot", "")
        if label not in existing:
            views.append({
                "perspective": label,
                "bot_name": base,
                "provider": None,
                "action": None,
                "ticker": None,
                "confidence": None,
                "reasoning": "No stored live view for this ticker yet.",
                "headline_used": None,
                "timestamp": None,
                "evidence_ids": [],
                "hold_cause": None,
                "status": "missing_live_view",
            })
    order = {"Analyst": 0, "Macro": 1, "Bear": 2}
    return sorted(views, key=lambda row: (order.get(row["perspective"], 99), row.get("provider") or ""))


def _brief_replay_context(symbol: str, replay_research: dict) -> dict:
    overall = replay_research.get("overall") or {} if replay_research.get("available") else {}
    ticker_rows = _load_replay_dataset_ticker_rows(symbol)
    trade_rows = [row for row in ticker_rows if row.get("action") in {"BUY", "SELL"}]
    return {
        "available": bool(replay_research.get("available")),
        "version": replay_research.get("version"),
        "overall": {
            "decision_count": overall.get("decision_count"),
            "trade_count": overall.get("trade_count"),
            "directional_accuracy_1d": overall.get("directional_accuracy_1d"),
            "beat_benchmark_rate_1d": overall.get("beat_benchmark_rate_1d"),
            "intent_mark_pnl_1d": overall.get("intent_mark_pnl_1d"),
        },
        "ticker": _summarize_replay_ticker_rows(symbol, trade_rows),
        "cost_summary": replay_research.get("cost_summary") or {},
    }


def _load_replay_dataset_ticker_rows(symbol: str, version: str = "v2") -> list[dict]:
    path = REPLAY_RESEARCH_DATASET_DIR / f"replay_decisions_{version}.csv"
    if not path.exists():
        return []
    rows = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str(row.get("ticker") or "").upper().strip() == symbol:
                    rows.append({
                        "action": str(row.get("action") or "").upper(),
                        "directional_correct_1d": _csv_bool(row.get("directional_correct_1d")),
                        "beat_benchmark_1d": _csv_bool(row.get("beat_benchmark_1d")),
                        "intent_mark_pnl_1d": _safe_number(row.get("intent_mark_pnl_1d")),
                        "risk_blocked": _csv_bool(row.get("risk_blocked")),
                    })
    except Exception:
        return []
    return rows


def _summarize_replay_ticker_rows(symbol: str, rows: list[dict]) -> dict:
    labeled_direction = [row for row in rows if row.get("directional_correct_1d") is not None]
    labeled_benchmark = [row for row in rows if row.get("beat_benchmark_1d") is not None]
    pnls = [row["intent_mark_pnl_1d"] for row in rows if row.get("intent_mark_pnl_1d") is not None]
    return {
        "ticker": symbol,
        "trade_count": len(rows),
        "risk_blocked_count": sum(1 for row in rows if row.get("risk_blocked") is True),
        "directional_accuracy_1d": _rate(labeled_direction, "directional_correct_1d"),
        "beat_benchmark_rate_1d": _rate(labeled_benchmark, "beat_benchmark_1d"),
        "intent_mark_pnl_1d": round(sum(pnls), 6) if pnls else None,
    }


def _brief_recommendation(
    *,
    symbol: str,
    trends: dict,
    agent_views: list[dict],
    evidence: list[dict],
    replay_context: dict,
) -> dict:
    periods = {
        row.get("period"): row
        for row in ((trends.get("ticker") or {}).get("periods") or [])
    }
    one_month = (periods.get("1m") or {}).get("return")
    three_month = (periods.get("3m") or {}).get("return")
    six_month = (periods.get("6m") or {}).get("return")
    live_views = [row for row in agent_views if row.get("status") == "available"]
    actions = [str(row.get("action") or "").upper() for row in live_views]
    buy_count = actions.count("BUY")
    sell_count = actions.count("SELL")
    hold_count = actions.count("HOLD")
    reasons = []

    if not live_views:
        category = "research_more"
        reasons.append("No stored live Analyst/Macro/Bear view exists for this ticker yet.")
    elif sell_count > buy_count and (one_month or 0) < 0:
        category = "reduce"
        reasons.append("Recent agent views lean defensive while the short-term trend is weak.")
    elif buy_count > sell_count and _positive(one_month) and _positive(three_month):
        category = "add"
        reasons.append("Agent views lean constructive and both 1-month and 3-month trends are positive.")
    elif not evidence:
        category = "research_more"
        reasons.append("No local evidence was retrieved for the ticker.")
    else:
        category = "wait"
        reasons.append("Signals are mixed enough that waiting is more honest than forcing a trade.")

    if one_month is not None:
        reasons.append(f"1-month replay-window trend is {_format_percent(one_month)}.")
    if three_month is not None:
        reasons.append(f"3-month replay-window trend is {_format_percent(three_month)}.")
    if six_month is not None:
        reasons.append(f"6-month replay-window trend is {_format_percent(six_month)}.")
    ticker_replay = (replay_context.get("ticker") or {})
    if ticker_replay.get("trade_count", 0) == 0:
        reasons.append("Replay has no ticker-specific trades for this name yet.")

    summary = f"{_category_label(category)} on {symbol}: {reasons[0] if reasons else 'Insufficient signal.'}"
    return {
        "category": category,
        "label": _category_label(category),
        "summary": summary,
        "confidence": _brief_confidence(category, live_views, evidence),
        "reasons": reasons[:6],
        "agent_action_counts": {
            "buy": buy_count,
            "hold": hold_count,
            "sell": sell_count,
        },
    }


def _brief_why_it_matters(symbol: str, trends: dict, evidence: list[dict], replay_context: dict) -> list[str]:
    rows = []
    ticker_periods = ((trends.get("ticker") or {}).get("periods") or [])
    one_month = next((row for row in ticker_periods if row.get("period") == "1m"), {})
    if one_month.get("return") is not None:
        rows.append(f"{symbol} moved {_format_percent(one_month['return'])} over the latest 1-month replay window.")
    comparisons = trends.get("comparisons") or []
    qqq_1m = next((row for row in comparisons if row.get("benchmark") == "QQQ" and row.get("period") == "1m"), None)
    if qqq_1m and qqq_1m.get("excess_return") is not None:
        rows.append(f"Versus QQQ over that window, excess return was {_format_percent(qqq_1m['excess_return'])}.")
    if evidence:
        rows.append(f"{len(evidence)} local evidence item(s) are available for this ticker.")
    else:
        rows.append("No local evidence items were retrieved yet, so the brief should stay cautious.")
    overall = replay_context.get("overall") or {}
    if overall.get("beat_benchmark_rate_1d") is not None:
        rows.append(f"Across the v2 replay, agents beat SPY on {_format_percent(overall['beat_benchmark_rate_1d'])} of labeled 1-day trades.")
    return rows


def _brief_decision_options(selected: str) -> list[dict]:
    labels = {
        "add": "Add",
        "wait": "Wait",
        "reduce": "Reduce",
        "research_more": "Research More",
    }
    descriptions = {
        "add": "Constructive signal; consider increasing exposure in the simulation.",
        "wait": "Mixed signal; keep watching before adding risk.",
        "reduce": "Defensive signal; consider lowering exposure or avoiding new adds.",
        "research_more": "Evidence or live-agent coverage is not strong enough yet.",
    }
    return [
        {
            "category": key,
            "label": label,
            "selected": key == selected,
            "description": descriptions[key],
        }
        for key, label in labels.items()
    ]


def _brief_risk_view(symbol: str, trends: dict, agent_views: list[dict], replay_context: dict) -> dict:
    risks = []
    bear_views = [row for row in agent_views if row.get("perspective") == "Bear" and row.get("status") == "available"]
    if bear_views:
        risks.append(bear_views[0].get("reasoning") or "Bear view is available but sparse.")
    ticker_replay = replay_context.get("ticker") or {}
    if ticker_replay.get("risk_blocked_count"):
        risks.append(f"Replay/risk layer blocked {ticker_replay['risk_blocked_count']} ticker-specific trade(s).")
    comparisons = trends.get("comparisons") or []
    weak = [row for row in comparisons if row.get("period") == "1m" and row.get("beat_benchmark") is False]
    if weak:
        risks.append(f"{symbol} lagged {weak[0]['benchmark']} over the latest 1-month replay window.")
    if not risks:
        risks.append("Main risk is insufficient live evidence for a confident decision.")
    return {
        "items": risks[:4],
        "stance": "cautious" if risks else "neutral",
    }


def _brief_change_triggers(symbol: str, category: str, trends: dict) -> list[str]:
    return [
        f"{symbol} starts beating QQQ on the 1-month and 3-month windows.",
        "Analyst and Macro views both turn constructive with cited evidence.",
        "Bear view identifies a concrete downside catalyst that invalidates the thesis.",
        "Fresh filing/news evidence changes demand, margin, capex, or guidance assumptions.",
        "Replay regression improves enough that ticker-specific trades beat SPY/QQQ after costs.",
    ][:5]


def _brief_caveats(replay_research: dict, recent_decisions: list[dict], evidence: list[dict]) -> list[str]:
    caveats = [
        "This is a simulated/research brief, not financial advice.",
        "Replay and no-orders intent PnL are not live investment performance.",
    ]
    if not recent_decisions:
        caveats.append("No stored live agent decision for this ticker was found yet.")
    if not evidence:
        caveats.append("No local RAG evidence was retrieved for this ticker.")
    cost = replay_research.get("cost_summary") or {}
    if replay_research.get("available") and not cost.get("available"):
        caveats.append("The historical v2 replay predates replay token/cost capture.")
    return caveats


def _base_bot_name(name: str | None) -> str:
    return str(name or "").split(" (", 1)[0].strip()


def _safe_number(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_bool(value) -> bool | None:
    raw = str(value or "").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no"}:
        return False
    return None


def _rate(rows: list[dict], field: str) -> float | None:
    if not rows:
        return None
    return round(sum(1 for row in rows if row.get(field) is True) / len(rows), 6)


def _positive(value) -> bool:
    return value is not None and value > 0


def _category_label(category: str) -> str:
    return {
        "add": "Add",
        "wait": "Wait",
        "reduce": "Reduce",
        "research_more": "Research More",
    }.get(category, "Research More")


def _brief_confidence(category: str, live_views: list[dict], evidence: list[dict]) -> float:
    score = 0.35
    if live_views:
        score += min(0.25, len(live_views) * 0.05)
    if evidence:
        score += min(0.2, len(evidence) * 0.04)
    if category == "research_more":
        score = min(score, 0.45)
    return round(score, 2)


def _format_percent(value) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _load_replay_fixtures() -> dict:
    fixtures = []
    errors = []
    for path in sorted(REPLAY_EVENTS_DIR.rglob("*.json")):
        if path.name.endswith(".report.json") or not _looks_like_replay_fixture(path):
            continue
        relative_path = path.relative_to(REPLAY_EVENTS_DIR).as_posix()
        try:
            name, config, events = load_replay_event_file(relative_path, root=REPLAY_EVENTS_DIR)
            fixtures.append(_replay_fixture_summary(path, relative_path, name, config, events))
        except Exception as exc:
            errors.append({"file_name": relative_path, "error": str(exc)})
    return {
        "fixtures": fixtures,
        "errors": errors,
        "default_providers": list(DEFAULT_PROVIDERS),
        "default_bots": list(DEFAULT_BOTS),
        "recommended_bots": ["analyst", "bear", "macro"],
        "default_execute_orders": False,
    }


def _load_replay_research(version: str = "v2") -> dict:
    paths = _replay_research_artifact_paths(version)
    standings = _load_json_if_exists(paths["standings"])
    if not standings:
        return {
            "available": False,
            "version": version,
            "error": f"Replay research standings for version '{version}' were not found.",
            "artifact_paths": _string_paths(paths),
            "expected_command": (
                "python scripts/refresh_replay_research.py --db sqlite:///replay.db "
                "--input-fingerprint <fingerprint> --benchmark SPY --version "
                f"{version} --output-dir data/ml"
            ),
        }

    model_suite = _load_json_if_exists(paths["model_suite"]) or {}
    manifest = _load_json_if_exists(paths["manifest"]) or {}
    dataset_summary = _load_json_if_exists(paths["dataset_summary"]) or {}
    markdown_report = _read_text_if_exists(paths["markdown_report"])

    return {
        "available": True,
        "version": version,
        "generated_at": standings.get("generated_at") or manifest.get("generated_at"),
        "benchmark": standings.get("benchmark") or dataset_summary.get("benchmark"),
        "overall": standings.get("overall") or {},
        "standings": standings.get("standings") or {},
        "lessons": standings.get("lessons") or {},
        "model_suite_summary": standings.get("model_suite_summary") or {},
        "model_suite": _compact_model_suite(model_suite),
        "dataset_summary": dataset_summary,
        "cost_summary": _replay_research_cost_summary(dataset_summary, standings),
        "manifest": manifest,
        "markdown_report": markdown_report,
        "artifact_paths": _string_paths(paths),
    }


def _replay_research_artifact_paths(version: str) -> dict[str, Path]:
    return {
        "standings": REPLAY_RESEARCH_REPORT_DIR / f"replay_standings_{version}.json",
        "model_suite": REPLAY_RESEARCH_REPORT_DIR / f"model_suite_{version}.json",
        "manifest": REPLAY_RESEARCH_REPORT_DIR / f"refresh_manifest_{version}.json",
        "markdown_report": REPLAY_RESEARCH_REPORT_DIR / f"replay_research_report_{version}.md",
        "dataset_summary": REPLAY_RESEARCH_DATASET_DIR / f"replay_decisions_{version}.summary.json",
        "feature_dictionary": REPLAY_RESEARCH_DATASET_DIR / f"feature_dictionary_{version}.md",
        "dataset": REPLAY_RESEARCH_DATASET_DIR / f"replay_decisions_{version}.csv",
    }


def _load_json_if_exists(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _read_text_if_exists(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _string_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in paths.items()}


def _compact_model_suite(model_suite: dict) -> dict:
    if not model_suite:
        return {}
    return {
        "generated_at": model_suite.get("generated_at"),
        "dataset": model_suite.get("dataset"),
        "row_count": model_suite.get("row_count"),
        "feature_columns": model_suite.get("feature_columns") or [],
        "model_names": model_suite.get("model_names") or [],
        "targets": {
            target: _compact_model_target(result)
            for target, result in (model_suite.get("targets") or {}).items()
        },
    }


def _compact_model_target(result: dict) -> dict:
    models = {}
    for name, model_result in (result.get("models") or {}).items():
        test = ((model_result.get("metrics") or {}).get("test") or {})
        models[name] = {
            "test_accuracy": test.get("accuracy"),
            "test_f1": test.get("f1"),
            "test_precision": test.get("precision"),
            "test_recall": test.get("recall"),
            "test_roc_auc": test.get("roc_auc"),
            "test_row_count": test.get("row_count"),
        }
    return {
        "status": result.get("status"),
        "usable_rows": result.get("usable_rows"),
        "label_counts": result.get("label_counts") or {},
        "warnings": result.get("warnings") or [],
        "split": result.get("split") or {},
        "best_model_by_test_accuracy": result.get("best_model_by_test_accuracy"),
        "best_model_by_test_f1": result.get("best_model_by_test_f1"),
        "models": models,
    }


def _replay_research_cost_summary(dataset_summary: dict, standings: dict | None = None) -> dict:
    cost_summary = dict(
        dataset_summary.get("cost_summary")
        or (standings or {}).get("cost_summary")
        or {}
    )
    recorded_count = int(cost_summary.get("recorded_cost_count") or 0)
    if cost_summary.get("available") or recorded_count > 0:
        cost_summary["available"] = True
        return cost_summary
    return {
        **cost_summary,
        "available": False,
        "recorded_cost_count": recorded_count,
        "total_estimated_llm_cost_usd": cost_summary.get("total_estimated_llm_cost_usd"),
        "reason": (
            "This replay report was generated from replay rows that did not store "
            "LLM token/cost fields. Exact spend cannot be reconstructed after the run; "
            "future replay runs record those fields."
        ),
    }


def _looks_like_replay_fixture(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return True
    if isinstance(payload, list):
        return True
    return isinstance(payload, dict) and isinstance(payload.get("events"), list)


def _replay_fixture_summary(
    path: Path,
    relative_path: str,
    name: str | None,
    config: dict,
    events: list[dict],
) -> dict:
    tickers = _fixture_tickers(config, events)
    timestamps = [
        str(event.get("as_of_time") or event.get("timestamp"))
        for event in events
        if event.get("as_of_time") or event.get("timestamp")
    ]
    timestamps = sorted(timestamps)
    recommended_bots = ["analyst", "bear", "macro"]
    event_path = f"data/replay_events/{relative_path}"
    return {
        "file_name": relative_path,
        "path": event_path,
        "name": name or path.stem.replace("_", " ").title(),
        "description": config.get("description") or _fixture_description(path),
        "scenario": config.get("scenario"),
        "event_count": len(events),
        "tickers": tickers,
        "start_time": timestamps[0] if timestamps else None,
        "end_time": timestamps[-1] if timestamps else None,
        "expected_notes": _fixture_expected_notes(config, events),
        "api_request": {
            "event_file": relative_path,
            "providers": list(DEFAULT_PROVIDERS),
            "bots": recommended_bots,
            "execute_orders": False,
            "name": name or path.stem.replace("_", " ").title(),
            "notes": "operator replay fixture run",
        },
        "single_run_command": (
            f"python scripts/run_replay.py --events {event_path} "
            "--providers claude,openai --bots analyst,bear,macro "
            "--db sqlite:///replay.db --no-orders"
        ),
        "matrix_command": (
            f"python scripts/run_replay_matrix.py --events {event_path} "
            "--provider-sets claude openai --bots analyst,bear,macro "
            "--db sqlite:///replay.db --no-orders "
            f"--report data/replay_runs/{path.stem}_matrix_report.json"
        ),
    }


def _fixture_description(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    if isinstance(payload, dict):
        value = payload.get("description")
        return str(value) if value else None
    return None


def _fixture_tickers(config: dict, events: list[dict]) -> list[str]:
    tickers = set()
    for ticker in config.get("tickers") or []:
        if ticker:
            tickers.add(str(ticker).upper())
    for event in events:
        for ticker in (event.get("prices") or {}).keys():
            tickers.add(str(ticker).upper())
        for ticker in (event.get("ticker_headlines") or {}).keys():
            tickers.add(str(ticker).upper())
    return sorted(tickers)


def _fixture_expected_notes(config: dict, events: list[dict]) -> list[str]:
    notes = []
    for value in config.get("expected_notes") or []:
        if value:
            notes.append(str(value))
    for event in events:
        for value in event.get("expected_notes") or []:
            if value:
                notes.append(str(value))
    deduped = []
    seen = set()
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        deduped.append(note)
    return deduped[:12]
