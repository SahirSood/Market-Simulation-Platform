"""Read-only operational status endpoints."""
import asyncio
import os
from urllib.parse import urlsplit, urlunsplit
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api import state as app_state
from api.audit import record_audit_event
from api.dependencies import WritePrincipal, require_write_auth
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
    return {
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


@router.get("/ops/ingestion/status")
async def get_ingestion_status():
    """Local ingestion configuration status."""
    state = app_state.get()
    repository = getattr(state, "rag_repository", None)
    return {
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
    }


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


def _job_summary(repository) -> dict:
    if repository is None:
        return {}
    summarize_job_status = getattr(repository, "summarize_job_status", None)
    if not callable(summarize_job_status):
        return {}
    return summarize_job_status()


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
