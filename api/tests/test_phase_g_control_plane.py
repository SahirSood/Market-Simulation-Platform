import asyncio
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from api import state as app_state
from api.dependencies import WritePrincipal, require_write_auth
from api.routers.audit import list_audit_events
from api.routers.evaluation import ReplayRunCreateRequest, create_replay_run
from api.routers.ops import (
    EmbeddingTriggerRequest,
    IngestionTriggerRequest,
    RagRequeueRequest,
    requeue_rag_jobs,
    run_embedding_once,
    run_ingestion_once,
)
from audit import AuditLog
from rag.repository import RagRepository
from replay import ReplayStore


class FakeEmbeddingService:
    def is_available(self):
        return True

    def embed_texts(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


def _db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'phase_g.db'}"


def _state_with_storage(tmp_path):
    db_url = _db_url(tmp_path)
    repository = RagRepository(db_url)
    repository.create_tables()
    audit_log = AuditLog(db_url)
    replay_store = ReplayStore(db_url)
    app_state.init(SimpleNamespace(
        bots=[],
        replay_store=replay_store,
        reasoning_log=None,
        rag_repository=repository,
        embedding_service=FakeEmbeddingService(),
        risk_limits=None,
        scheduler=None,
        audit_log=audit_log,
    ))
    return repository, audit_log, replay_store


def test_require_write_auth_returns_principal(monkeypatch):
    monkeypatch.setenv("ARENA_API_KEY", "secret")

    principal = asyncio.run(
        require_write_auth(
            x_api_key="secret",
            x_actor="operator",
            x_request_id="req-1",
        )
    )

    assert principal.actor == "operator"
    assert principal.auth_method == "arena_api_key"
    assert principal.request_id == "req-1"


def test_require_write_auth_rejects_invalid_key(monkeypatch):
    monkeypatch.setenv("ARENA_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_write_auth(x_api_key="wrong"))

    assert exc.value.status_code == 401


def test_create_replay_run_requires_valid_events_and_audits(tmp_path):
    repository, audit_log, replay_store = _state_with_storage(tmp_path)
    repository.add_document_with_chunks(
        ticker="AAPL",
        title="AAPL 10-Q",
        source_url="https://example.com/aapl",
        content="revenue margin",
        chunks=[{"content": "revenue margin", "start_pos": 0, "end_pos": 14}],
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    request = ReplayRunCreateRequest(
        name="api replay",
        events=[
            {
                "timestamp": "2026-01-02T00:00:00Z",
                "prices": {"AAPL": 100.0},
                "recent_headlines": ["AAPL revenue rises"],
            }
        ],
        providers=["claude"],
        bots=["bear"],
        execute_orders=False,
    )

    result = asyncio.run(
        create_replay_run(request, WritePrincipal(actor="operator", request_id="req-1"))
    )

    assert result["status"] == "completed"
    assert result["decision_count"] == 1
    assert replay_store.get_run(result["run_id"])["config"]["execution_mode"] == "isolated_replay"
    events = audit_log.list_events(action="replay.run.create")
    assert events[0]["target_id"] == result["run_id"]
    assert events[0]["actor"] == "operator"


def test_embedding_and_requeue_write_endpoints_audit(tmp_path):
    repository, audit_log, _ = _state_with_storage(tmp_path)
    repository.add_document_with_chunks(
        ticker="AAPL",
        title="AAPL 10-Q",
        source_url="https://example.com/aapl",
        content="revenue margin",
        chunks=[{"content": "revenue margin", "start_pos": 0, "end_pos": 14}],
    )
    failed_job_id = repository.start_job("embedding", metadata={"limit": 5}, max_attempts=2)
    repository.update_job_status(failed_job_id, "failed", attempts=2, error="temporary outage")
    principal = WritePrincipal(actor="operator", request_id="req-2")

    embedded = asyncio.run(
        run_embedding_once(
            EmbeddingTriggerRequest(limit=10, batch_size=2),
            principal,
        )
    )
    requeued = asyncio.run(
        requeue_rag_jobs(
            RagRequeueRequest(job_type="embedding", statuses=["failed"], limit=10),
            principal,
        )
    )

    assert embedded["embedded"] == 1
    assert requeued["requeued_count"] == 1
    actions = [row["action"] for row in audit_log.list_events(limit=10)]
    assert "ops.embedding.run" in actions
    assert "ops.rag.requeue" in actions


def test_ingestion_write_endpoint_audits(monkeypatch, tmp_path):
    _, audit_log, _ = _state_with_storage(tmp_path)

    def fake_poll(tickers, db_url, max_filings, forms, repository, ingestion_service, max_retries):
        return {
            "tracked_ciks": ["0000320193"],
            "unknown_tickers": [],
            "detected": {},
            "updated_tickers": ["AAPL"],
        }

    monkeypatch.setattr("api.routers.ops.poll_and_ingest_once", fake_poll)

    result = asyncio.run(
        run_ingestion_once(
            IngestionTriggerRequest(tickers=["AAPL"], max_filings=1, forms=["10-Q"]),
            WritePrincipal(actor="operator", request_id="req-3"),
        )
    )

    assert result["updated_tickers"] == ["AAPL"]
    event = audit_log.list_events(action="ops.ingestion.run")[0]
    assert event["metadata"]["updated_tickers"] == ["AAPL"]


def test_missing_repository_write_attempt_is_audited(tmp_path):
    audit_log = AuditLog(_db_url(tmp_path))
    app_state.init(SimpleNamespace(rag_repository=None, audit_log=audit_log))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            run_embedding_once(
                EmbeddingTriggerRequest(limit=10, batch_size=2),
                WritePrincipal(actor="operator", request_id="req-4"),
            )
        )

    assert exc.value.status_code == 404
    event = audit_log.list_events(action="ops.embedding.run")[0]
    assert event["status"] == "failed"
    assert event["error"] == "RAG repository is not configured"


def test_audit_events_endpoint_is_protected_data(tmp_path):
    _, audit_log, _ = _state_with_storage(tmp_path)
    audit_log.record_event(
        "ops.rag.requeue",
        actor="operator",
        auth_method="arena_api_key",
        status="succeeded",
    )

    result = asyncio.run(
        list_audit_events(
            limit=10,
            principal=WritePrincipal(actor="operator"),
        )
    )

    assert result["events"][0]["action"] == "ops.rag.requeue"
    assert result["principal"]["actor"] == "operator"
