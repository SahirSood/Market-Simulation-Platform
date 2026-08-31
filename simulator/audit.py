"""Durable audit records for protected control-plane actions."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


logger = logging.getLogger(__name__)


class AuditBase(DeclarativeBase):
    pass


class AuditEventRecord(AuditBase):
    __tablename__ = "phase_g_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    auth_method: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class AuditLog:
    """Append-only audit store.

    Audit writes are best-effort from the API caller's perspective: control-plane
    actions should not fail because the audit database has a transient issue, but
    failures are logged loudly for local operators.
    """

    def __init__(self, database_url: str = "sqlite:///:memory:", echo: bool = False):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            echo=echo,
            **({} if database_url.startswith("sqlite") else {
                "pool_size": 5,
                "max_overflow": 2,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
            }),
        )
        self.create_tables()

    def create_tables(self) -> None:
        AuditBase.metadata.create_all(self.engine)

    def record_event(
        self,
        action: str,
        *,
        actor: str = "unknown",
        auth_method: str = "unknown",
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        status: str = "succeeded",
        metadata: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[int]:
        try:
            record = AuditEventRecord(
                timestamp=datetime.now(timezone.utc),
                actor=str(actor or "unknown")[:128],
                auth_method=str(auth_method or "unknown")[:64],
                action=str(action)[:128],
                target_type=str(target_type)[:64] if target_type is not None else None,
                target_id=str(target_id)[:128] if target_id is not None else None,
                status=str(status)[:32],
                request_id=str(request_id)[:128] if request_id else None,
                error=str(error)[:2000] if error else None,
                metadata_json=_json_safe(metadata or {}),
            )
            with Session(self.engine) as session:
                session.add(record)
                session.commit()
                return int(record.id)
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.error("Audit write failed for action=%s: %s", action, exc)
            return None

    def list_events(
        self,
        *,
        limit: int = 100,
        action: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        with Session(self.engine) as session:
            query = session.query(AuditEventRecord).order_by(AuditEventRecord.timestamp.desc())
            if action:
                query = query.filter(AuditEventRecord.action == action)
            if status:
                query = query.filter(AuditEventRecord.status == status)
            rows = query.limit(max(1, int(limit))).all()
            return [_event_to_dict(row) for row in rows]


def _event_to_dict(row: AuditEventRecord) -> dict:
    return {
        "id": row.id,
        "timestamp": row.timestamp,
        "actor": row.actor,
        "auth_method": row.auth_method,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "status": row.status,
        "request_id": row.request_id,
        "error": row.error,
        "metadata": row.metadata_json or {},
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
