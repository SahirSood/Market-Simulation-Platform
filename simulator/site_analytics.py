"""First-party site analytics for the public deployed dashboard."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import DateTime, Integer, JSON, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class SiteAnalyticsBase(DeclarativeBase):
    pass


class SiteAnalyticsEventRecord(SiteAnalyticsBase):
    __tablename__ = "site_analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    utm_source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    utm_medium: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SiteAnalyticsStore:
    def __init__(self, database_url: str = "sqlite:///:memory:", echo: bool = False):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            echo=echo,
            **({} if database_url.startswith("sqlite") else {"pool_size": 5, "max_overflow": 2}),
        )
        self.create_tables()

    def create_tables(self) -> None:
        SiteAnalyticsBase.metadata.create_all(self.engine)

    def record_event(
        self,
        *,
        event_type: str,
        path: str,
        url: Optional[str] = None,
        title: Optional[str] = None,
        referrer: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        target_url: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        referrer_domain = _domain(referrer)
        target_domain = _domain(target_url)
        source = _clean(utm_source, 128) or referrer_domain or "direct"
        record = SiteAnalyticsEventRecord(
            timestamp=datetime.now(timezone.utc),
            event_type=_clean(event_type, 32) or "pageview",
            path=_clean(path, 512) or "/",
            url=_clean(url, 4096),
            title=_clean(title, 256),
            referrer=_clean(referrer, 4096),
            referrer_domain=referrer_domain,
            source=_clean(source, 128) or "direct",
            utm_source=_clean(utm_source, 128),
            utm_medium=_clean(utm_medium, 128),
            utm_campaign=_clean(utm_campaign, 128),
            target_url=_clean(target_url, 4096),
            target_domain=target_domain,
            session_id=_clean(session_id, 128),
            ip_hash=_hash_ip(ip_address),
            user_agent=_clean(user_agent, 512),
            metadata_json=_json_safe(metadata or {}),
        )
        with Session(self.engine) as session:
            session.add(record)
            session.commit()
            return int(record.id)

    def summary(self, *, days: int = 30, limit: int = 20) -> dict[str, Any]:
        days = max(1, min(int(days), 365))
        limit = max(1, min(int(limit), 100))
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with Session(self.engine) as session:
            base = session.query(SiteAnalyticsEventRecord).filter(
                SiteAnalyticsEventRecord.timestamp >= since
            )
            total_events = base.with_entities(func.count(SiteAnalyticsEventRecord.id)).scalar() or 0
            pageviews = (
                base.with_entities(func.count(SiteAnalyticsEventRecord.id))
                .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                .scalar()
                or 0
            )
            outbound_clicks = (
                base.with_entities(func.count(SiteAnalyticsEventRecord.id))
                .filter(SiteAnalyticsEventRecord.event_type == "outbound_click")
                .scalar()
                or 0
            )
            unique_sessions = (
                base.with_entities(func.count(func.distinct(SiteAnalyticsEventRecord.session_id)))
                .filter(SiteAnalyticsEventRecord.session_id.isnot(None))
                .scalar()
                or 0
            )
            unique_visitors = (
                base.with_entities(func.count(func.distinct(SiteAnalyticsEventRecord.ip_hash)))
                .filter(SiteAnalyticsEventRecord.ip_hash.isnot(None))
                .scalar()
                or 0
            )
            return {
                "window_days": days,
                "total_events": int(total_events),
                "pageviews": int(pageviews),
                "outbound_clicks": int(outbound_clicks),
                "unique_sessions": int(unique_sessions),
                "unique_visitors": int(unique_visitors),
                "by_day": _pairs(
                    base.with_entities(
                        func.date(SiteAnalyticsEventRecord.timestamp),
                        func.count(SiteAnalyticsEventRecord.id),
                    )
                    .group_by(func.date(SiteAnalyticsEventRecord.timestamp))
                    .order_by(func.date(SiteAnalyticsEventRecord.timestamp).desc())
                    .limit(days)
                    .all(),
                    "date",
                ),
                "top_sources": _pairs(
                    base.with_entities(SiteAnalyticsEventRecord.source, func.count(SiteAnalyticsEventRecord.id))
                    .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                    .group_by(SiteAnalyticsEventRecord.source)
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all(),
                    "source",
                ),
                "top_paths": _pairs(
                    base.with_entities(SiteAnalyticsEventRecord.path, func.count(SiteAnalyticsEventRecord.id))
                    .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                    .group_by(SiteAnalyticsEventRecord.path)
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all(),
                    "path",
                ),
                "top_outbound_targets": _pairs(
                    base.with_entities(SiteAnalyticsEventRecord.target_domain, func.count(SiteAnalyticsEventRecord.id))
                    .filter(SiteAnalyticsEventRecord.event_type == "outbound_click")
                    .group_by(SiteAnalyticsEventRecord.target_domain)
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all(),
                    "target_domain",
                ),
                "recent_events": [
                    _event_to_dict(row)
                    for row in base
                    .order_by(SiteAnalyticsEventRecord.timestamp.desc())
                    .limit(limit)
                    .all()
                ],
            }


def _event_to_dict(row: SiteAnalyticsEventRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "timestamp": row.timestamp,
        "event_type": row.event_type,
        "path": row.path,
        "source": row.source,
        "referrer_domain": row.referrer_domain,
        "utm_source": row.utm_source,
        "utm_medium": row.utm_medium,
        "utm_campaign": row.utm_campaign,
        "target_domain": row.target_domain,
        "target_url": row.target_url,
        "session_id": row.session_id,
    }


def _pairs(rows, key_name: str) -> list[dict[str, Any]]:
    return [{key_name: str(key or "unknown"), "count": int(count or 0)} for key, count in rows]


def _domain(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parsed = urlparse(value)
    return _clean(parsed.netloc.lower(), 255) if parsed.netloc else None


def _hash_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    salt = os.getenv("SITE_ANALYTICS_SALT") or os.getenv("ARENA_API_KEY") or "market-simulation-platform"
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()


def _clean(value: Optional[Any], max_len: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:max_len] if text else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, str, int, float, bool)) or value is None:
        return value.isoformat() if isinstance(value, datetime) else value
    return str(value)
