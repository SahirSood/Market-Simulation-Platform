"""Read-only operational status endpoints."""
import asyncio
import os
from urllib.parse import urlsplit, urlunsplit
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api import state as app_state
from api.audit import record_audit_event
from api.dependencies import (
    WritePrincipal,
    public_ops_detail_enabled,
    public_read_only_mode_enabled,
    require_write_auth,
)
from news_feed import is_news_api_configured
from scripts.embed_worker import embed_once
from scripts.ingest_poller import poll_and_ingest_once

router = APIRouter()


class IngestionTriggerRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "NVDA"])
    max_filings: int = Field(default=2, ge=1, le=10)
    forms: list[str] = Field(default_factory=lambda: ["10-K", "10-Q", "8-K"])
    max_retries: int = Field(default=0, ge=0, le=3)


class EmbeddingTriggerRequest(BaseModel):
    limit: int = Field(default=1000, ge=1, le=5000)
    batch_size: int = Field(default=64, ge=1, le=256)
    max_retries: int = Field(default=0, ge=0, le=3)


class RagRequeueRequest(BaseModel):
    job_type: Literal["ingestion", "embedding"] | None = None
    statuses: list[str] = Field(default_factory=lambda: ["failed"])
    limit: int = Field(default=20, ge=1, le=200)


@router.get("/ops/rag/status")
async def get_rag_status():
    """RAG storage and embedding queue status."""
    state = app_state.get()
    repository = getattr(state, "rag_repository", None)
    if repository is None:
        return {
            "configured": False,
            "document_count": 0,
            "chunk_count": 0,
            "pending_embedding_count_sample": None,
        }

    pending_sample = None
    if hasattr(repository, "get_chunks_without_embeddings"):
        pending_sample = len(repository.get_chunks_without_embeddings(limit=100))
    payload = {
        "configured": True,
        "engine_url": _redact_database_url(getattr(repository, "engine_url", None)),
        "document_count": repository.count_documents(),
        "chunk_count": repository.count_chunks(),
        "pending_embedding_count_sample": pending_sample,
        "embedding_service_configured": bool(getattr(state, "embedding_service", None)),
        "write_auth_configured": bool(os.getenv("ARENA_API_KEY")),
        "audit_log_configured": bool(getattr(state, "audit_log", None)),
        "job_summary": _job_summary(repository),
        "recent_embedding_jobs": _recent_jobs(repository, "embedding"),
    }
    if public_read_only_mode_enabled() and not public_ops_detail_enabled():
        return {
            "configured": True,
            "document_count": payload["document_count"],
            "chunk_count": payload["chunk_count"],
            "pending_embedding_count_sample": pending_sample,
            "embedding_service_configured": payload["embedding_service_configured"],
        }
    return payload


@router.get("/ops/rag/catalog")
async def get_rag_catalog():
    """Document-library totals and filter facets for the RAG store."""
    state = app_state.get()
    repository = _require_repository(state)
    summarize = getattr(repository, "summarize_documents", None)
    if not callable(summarize):
        raise HTTPException(501, "RAG repository does not support document catalog summaries")

    summary = await asyncio.to_thread(summarize)
    duplicate_audit = {
        "duplicate_group_count": 0,
        "duplicate_document_count": 0,
        "duplicate_chunk_count": 0,
    }
    audit_duplicates = getattr(repository, "deduplicate_documents", None)
    if callable(audit_duplicates):
        audit_result = await asyncio.to_thread(audit_duplicates, True)
        duplicate_audit = {
            "duplicate_group_count": int(audit_result.get("duplicate_group_count") or 0),
            "duplicate_document_count": int(audit_result.get("duplicate_document_count") or 0),
            "duplicate_chunk_count": int(audit_result.get("duplicate_chunk_count") or 0),
        }
    payload = {
        "configured": True,
        **summary,
        **duplicate_audit,
        "recent_ingestion_jobs": _recent_jobs(repository, "ingestion"),
        "recent_embedding_jobs": _recent_jobs(repository, "embedding"),
        "research_events": _recent_research_events(state),
    }
    if public_read_only_mode_enabled() and not public_ops_detail_enabled():
        payload.pop("recent_ingestion_jobs", None)
        payload.pop("recent_embedding_jobs", None)
        payload.pop("research_events", None)
    return payload


@router.get("/ops/rag/documents")
async def list_rag_documents(
    ticker: str | None = Query(None),
    source_type: str | None = Query(None),
    form_type: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Browse ingested RAG documents without returning full document content."""
    state = app_state.get()
    repository = _require_repository(state)
    list_documents = getattr(repository, "list_documents", None)
    if not callable(list_documents):
        raise HTTPException(501, "RAG repository does not support document listing")

    result = await asyncio.to_thread(
        list_documents,
        _clean_filter(ticker),
        _clean_filter(source_type),
        _clean_filter(form_type),
        _clean_filter(q),
        limit,
        offset,
    )
    documents = result.get("documents", [])
    _decorate_rag_documents(state, repository, documents)
    return result


@router.get("/ops/rag/documents/{document_id}")
async def get_rag_document(document_id: int, chunk_limit: int = Query(12, ge=1, le=50)):
    """One ingested document with bounded chunk excerpts."""
    state = app_state.get()
    repository = _require_repository(state)
    get_detail = getattr(repository, "get_document_detail", None)
    if not callable(get_detail):
        raise HTTPException(501, "RAG repository does not support document details")

    document = await asyncio.to_thread(get_detail, document_id, chunk_limit)
    if document is None:
        raise HTTPException(404, "RAG document not found")
    _decorate_rag_documents(state, repository, [document])
    return document


@router.get("/ops/ingestion/status")
async def get_ingestion_status():
    """Local ingestion configuration status."""
    state = app_state.get()
    repository = getattr(state, "rag_repository", None)
    research_coordinator = getattr(state, "research_coordinator", None)
    scheduler = getattr(state, "scheduler", None)
    payload = {
        "sec_user_agent_configured": bool(os.getenv("SEC_USER_AGENT")),
        "database_url_configured": bool(os.getenv("DATABASE_URL")),
        "news_api_configured": is_news_api_configured(os.getenv("NEWS_API_KEY")),
        "mcp_http_configured": bool(
            os.getenv("AGENT_MCP_HTTP_TOKEN")
            or os.getenv("AGENT_MCP_TOKEN")
            or os.getenv("ARENA_API_KEY")
        ),
        "write_auth_configured": bool(os.getenv("ARENA_API_KEY")),
        "audit_log_configured": bool(getattr(state, "audit_log", None)),
        "job_backend": "local_scripts",
        "poller_command": "python scripts/ingest_poller.py --once --tickers AAPL MSFT --db sqlite:///rag.db",
        "embedding_command": "python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64",
        "job_summary": _job_summary(repository),
        "recent_ingestion_jobs": _recent_jobs(repository, "ingestion"),
        "research": research_coordinator.status() if research_coordinator is not None else {"enabled": False},
        "scheduler": scheduler.status() if scheduler is not None and hasattr(scheduler, "status") else {},
    }
    if public_read_only_mode_enabled() and not public_ops_detail_enabled():
        return {
            "public_read_only": True,
            "live_data": {
                "news_available": payload["news_api_configured"],
                "sec_filings_available": bool(repository),
            },
            "rag": {
                "configured": bool(repository),
                "job_summary": _public_job_summary(payload.get("job_summary") or {}),
            },
            "scheduler": _public_scheduler_status(payload.get("scheduler") or {}),
        }
    return payload


@router.post("/ops/ingestion/run")
async def run_ingestion_once(
    request: IngestionTriggerRequest,
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Protected one-shot SEC filing detection and ingestion trigger."""
    state = app_state.get()
    try:
        repository = _require_repository(state)
        result = await asyncio.to_thread(
            poll_and_ingest_once,
            request.tickers,
            getattr(repository, "engine_url", None) or os.getenv("DATABASE_URL") or "sqlite:///rag.db",
            request.max_filings,
            request.forms,
            repository,
            None,
            request.max_retries,
        )
        record_audit_event(
            state,
            principal,
            "ops.ingestion.run",
            target_type="rag_job",
            metadata={
                "tickers": [ticker.upper() for ticker in request.tickers],
                "forms": request.forms,
                "max_filings": request.max_filings,
                "max_retries": request.max_retries,
                "updated_tickers": result.get("updated_tickers", []),
                "unknown_tickers": result.get("unknown_tickers", []),
            },
        )
        return result
    except HTTPException as exc:
        record_audit_event(
            state,
            principal,
            "ops.ingestion.run",
            target_type="rag_job",
            status="failed",
            metadata={
                "tickers": [ticker.upper() for ticker in request.tickers],
                "forms": request.forms,
                "max_filings": request.max_filings,
                "max_retries": request.max_retries,
            },
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        record_audit_event(
            state,
            principal,
            "ops.ingestion.run",
            target_type="rag_job",
            status="failed",
            metadata={
                "tickers": [ticker.upper() for ticker in request.tickers],
                "forms": request.forms,
                "max_filings": request.max_filings,
                "max_retries": request.max_retries,
            },
            error=str(exc),
        )
        raise HTTPException(500, f"Ingestion run failed: {exc}")


@router.post("/ops/embedding/run")
async def run_embedding_once(
    request: EmbeddingTriggerRequest,
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Protected one-shot embedding trigger for chunks without embeddings."""
    state = app_state.get()
    try:
        repository = _require_repository(state)
        embedded = await asyncio.to_thread(
            embed_once,
            getattr(repository, "engine_url", None) or os.getenv("DATABASE_URL") or "sqlite:///rag.db",
            request.limit,
            request.batch_size,
            repository,
            getattr(state, "embedding_service", None),
            request.max_retries,
        )
        record_audit_event(
            state,
            principal,
            "ops.embedding.run",
            target_type="rag_job",
            metadata={
                "limit": request.limit,
                "batch_size": request.batch_size,
                "max_retries": request.max_retries,
                "embedded": embedded,
            },
        )
        return {"embedded": embedded}
    except HTTPException as exc:
        record_audit_event(
            state,
            principal,
            "ops.embedding.run",
            target_type="rag_job",
            status="failed",
            metadata={
                "limit": request.limit,
                "batch_size": request.batch_size,
                "max_retries": request.max_retries,
            },
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        record_audit_event(
            state,
            principal,
            "ops.embedding.run",
            target_type="rag_job",
            status="failed",
            metadata={
                "limit": request.limit,
                "batch_size": request.batch_size,
                "max_retries": request.max_retries,
            },
            error=str(exc),
        )
        raise HTTPException(500, f"Embedding run failed: {exc}")


@router.post("/ops/rag/requeue")
async def requeue_rag_jobs(
    request: RagRequeueRequest,
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Protected requeue for failed/skipped local RAG job rows."""
    state = app_state.get()
    try:
        repository = _require_repository(state)
        jobs = await asyncio.to_thread(
            repository.requeue_jobs,
            job_type=request.job_type,
            statuses=request.statuses,
            limit=request.limit,
        )
        record_audit_event(
            state,
            principal,
            "ops.rag.requeue",
            target_type="rag_job",
            metadata={
                "job_type": request.job_type,
                "statuses": request.statuses,
                "limit": request.limit,
                "requeued_count": len(jobs),
                "job_ids": [row.get("id") for row in jobs],
            },
        )
        return {
            "requeued_count": len(jobs),
            "jobs": jobs,
            "next_step": _next_step(request.job_type),
        }
    except HTTPException as exc:
        record_audit_event(
            state,
            principal,
            "ops.rag.requeue",
            target_type="rag_job",
            status="failed",
            metadata={
                "job_type": request.job_type,
                "statuses": request.statuses,
                "limit": request.limit,
            },
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        record_audit_event(
            state,
            principal,
            "ops.rag.requeue",
            target_type="rag_job",
            status="failed",
            metadata={
                "job_type": request.job_type,
                "statuses": request.statuses,
                "limit": request.limit,
            },
            error=str(exc),
        )
        raise HTTPException(500, f"RAG requeue failed: {exc}")


def _recent_jobs(repository, job_type: str) -> list[dict]:
    if repository is None:
        return []
    list_job_status = getattr(repository, "list_job_status", None)
    if not callable(list_job_status):
        return []
    return list_job_status(job_type=job_type, limit=5)


def _recent_ingestion_jobs(repository, limit: int = 100) -> list[dict]:
    list_job_status = getattr(repository, "list_job_status", None)
    if not callable(list_job_status):
        return []
    return list_job_status(job_type="ingestion", limit=limit)


def _recent_research_events(state) -> list[dict]:
    research_coordinator = getattr(state, "research_coordinator", None)
    if research_coordinator is None or not hasattr(research_coordinator, "status"):
        return []
    try:
        status = research_coordinator.status()
    except Exception:
        return []
    return list(status.get("recent_events") or [])[:20]


def _decorate_rag_documents(state, repository, documents: list[dict]) -> None:
    if not documents:
        return
    citation_counts = _citation_counts_by_document(state, repository, documents)
    ingestion_jobs = _recent_ingestion_jobs(repository)
    research_events = _recent_research_events(state)
    for doc in documents:
        doc["category"] = _document_category(doc)
        doc["citation_count"] = citation_counts.get(int(doc.get("id") or 0), 0)
        reason, job = _infer_ingestion_reason(doc, ingestion_jobs, research_events)
        doc["ingestion_reason"] = reason
        doc["ingestion_job"] = job


def _citation_counts_by_document(state, repository, documents: list[dict]) -> dict[int, int]:
    get_chunk_id_map = getattr(repository, "get_document_chunk_id_map", None)
    reasoning_log = getattr(state, "reasoning_log", None)
    get_decisions = getattr(reasoning_log, "get_decisions", None)
    if not callable(get_chunk_id_map) or not callable(get_decisions):
        return {}

    document_ids = [int(doc["id"]) for doc in documents if doc.get("id") is not None]
    chunk_map = get_chunk_id_map(document_ids)
    chunk_to_document = {
        int(chunk_id): int(document_id)
        for document_id, chunk_ids in chunk_map.items()
        for chunk_id in chunk_ids
    }
    if not chunk_to_document:
        return {}

    counts = {document_id: 0 for document_id in document_ids}
    try:
        decisions = get_decisions(limit=1000)
    except Exception:
        return counts

    for decision in decisions:
        for raw_id in decision.get("evidence_ids") or []:
            try:
                chunk_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            document_id = chunk_to_document.get(chunk_id)
            if document_id is not None:
                counts[document_id] = counts.get(document_id, 0) + 1
    return counts


def _document_category(doc: dict) -> str:
    source_type = str(doc.get("source_type") or "").lower()
    form_type = str(doc.get("form_type") or "").upper()
    if "earnings" in source_type:
        return "Earnings"
    if source_type.startswith("sec"):
        if form_type == "10-K":
            return "Annual SEC filing"
        if form_type == "10-Q":
            return "Quarterly SEC filing"
        if form_type == "8-K":
            return "SEC event filing"
        return "SEC filing"
    if "news" in source_type:
        return "News"
    return source_type.replace("_", " ").title() if source_type else "Document"


def _infer_ingestion_reason(doc: dict, jobs: list[dict], research_events: list[dict]) -> tuple[str, dict | None]:
    ticker = str(doc.get("ticker") or "").upper()
    form_type = str(doc.get("form_type") or "").upper()

    for event in research_events:
        if str(event.get("ticker") or "").upper() != ticker:
            continue
        source_bot = event.get("source_bot")
        action = str(event.get("reason") or "").upper()
        if source_bot:
            return (
                f"Bot-requested research after {source_bot} considered a {action or 'trade'} on {ticker}.",
                None,
            )

    for job in jobs:
        metadata = job.get("metadata") or {}
        tickers = _metadata_tickers(metadata)
        if ticker and ticker in tickers:
            forms = metadata.get("forms") or []
            form_text = ", ".join(forms) if isinstance(forms, list) and forms else form_type or "SEC forms"
            return (
                f"SEC filing poll for {ticker}; requested {form_text} evidence for bot decisions.",
                {
                    "id": job.get("id"),
                    "status": job.get("status"),
                    "started_at": job.get("started_at"),
                    "finished_at": job.get("finished_at"),
                },
            )

    if str(doc.get("source_type") or "").lower().startswith("sec"):
        return (
            f"Baseline {form_type or 'SEC'} evidence coverage for {ticker or 'the market'} RAG citations.",
            None,
        )
    return "Stored as retrievable evidence for bot reasoning.", None


def _metadata_tickers(metadata: dict) -> set[str]:
    values: set[str] = set()
    for key in ("tickers", "updated_tickers"):
        raw = metadata.get(key)
        if isinstance(raw, list):
            values.update(str(value).upper() for value in raw if value)
    return values


def _clean_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _job_summary(repository) -> dict:
    if repository is None:
        return {}
    summarize_job_status = getattr(repository, "summarize_job_status", None)
    if not callable(summarize_job_status):
        return {}
    return summarize_job_status()


def _public_job_summary(summary: dict) -> dict:
    return {
        "total": int(summary.get("total") or 0),
        "by_status": dict(summary.get("by_status") or {}),
        "latest_finished_at": summary.get("latest_finished_at"),
    }


def _public_scheduler_status(status: dict) -> dict:
    keys = {
        "running",
        "market_hours_only",
        "market_open",
        "market_timezone",
        "market_open_time",
        "market_close_time",
        "cost_guard_enabled",
        "daily_estimated_llm_cost_usd",
        "monthly_estimated_llm_cost_usd",
        "daily_spend_limit_usd",
        "monthly_spend_limit_usd",
        "decision_budget_exhausted",
        "spend_budget_exhausted",
    }
    return {key: status.get(key) for key in keys if key in status}


def _require_repository(state):
    repository = getattr(state, "rag_repository", None)
    if repository is None:
        raise HTTPException(404, "RAG repository is not configured")
    return repository


def _redact_database_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    except Exception:
        return "<configured>"


def _next_step(job_type: str | None) -> str:
    if job_type == "embedding":
        return "Run scripts/embed_worker.py with the same database or POST /ops/embedding/run."
    if job_type == "ingestion":
        return "Run scripts/ingest_poller.py with the same database or POST /ops/ingestion/run."
    return "Run the relevant ingestion or embedding worker with the same database."
