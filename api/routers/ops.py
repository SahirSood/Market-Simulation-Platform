"""Read-only operational status endpoints."""
import os
from fastapi import APIRouter

from api import state as app_state

router = APIRouter()


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
        "engine_url": getattr(repository, "engine_url", None),
        "document_count": repository.count_documents(),
        "chunk_count": repository.count_chunks(),
        "pending_embedding_count_sample": pending_sample,
        "embedding_service_configured": bool(getattr(state, "embedding_service", None)),
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
        "news_api_configured": bool(os.getenv("NEWS_API_KEY")),
        "mcp_http_configured": bool(os.getenv("AGENT_MCP_HTTP_TOKEN") or os.getenv("AGENT_MCP_TOKEN")),
        "job_backend": "local_scripts",
        "poller_command": "python scripts/ingest_poller.py --once --tickers AAPL MSFT --db sqlite:///rag.db",
        "embedding_command": "python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64",
        "job_summary": _job_summary(repository),
        "recent_ingestion_jobs": _recent_jobs(repository, "ingestion"),
    }


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
