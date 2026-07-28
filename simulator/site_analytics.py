"""First-party site analytics for the public deployed dashboard."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, create_engine, func, inspect, text
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
    geo_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    geo_country_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    geo_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    geo_city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    geo_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    geo_continent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geo_org: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    geo_asn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geo_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
        self._ensure_optional_columns()

    def _ensure_optional_columns(self) -> None:
        inspector = inspect(self.engine)
        if "site_analytics_events" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("site_analytics_events")}
        optional_columns = {
            "geo_country": "VARCHAR(128)",
            "geo_country_code": "VARCHAR(8)",
            "geo_region": "VARCHAR(128)",
            "geo_city": "VARCHAR(128)",
            "geo_timezone": "VARCHAR(64)",
            "geo_continent": "VARCHAR(64)",
            "geo_org": "VARCHAR(255)",
            "geo_asn": "VARCHAR(64)",
            "geo_latitude": "FLOAT",
            "geo_longitude": "FLOAT",
            "geo_source": "VARCHAR(32)",
        }
        with self.engine.begin() as conn:
            for name, column_type in optional_columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE site_analytics_events ADD COLUMN {name} {column_type}"))

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
        geo: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        referrer_domain = _domain(referrer)
        target_domain = _domain(target_url)
        source = _clean(utm_source, 128) or referrer_domain or "direct"
        geo = geo or {}
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
            geo_country=_clean(geo.get("country"), 128),
            geo_country_code=_clean(geo.get("country_code"), 8),
            geo_region=_clean(geo.get("region"), 128),
            geo_city=_clean(geo.get("city"), 128),
            geo_timezone=_clean(geo.get("timezone"), 64),
            geo_continent=_clean(geo.get("continent"), 64),
            geo_org=_clean(geo.get("org"), 255),
            geo_asn=_clean(geo.get("asn"), 64),
            geo_latitude=_float_or_none(geo.get("latitude")),
            geo_longitude=_float_or_none(geo.get("longitude")),
            geo_source=_clean(geo.get("source"), 32),
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
                "top_countries": _pairs(
                    base.with_entities(
                        SiteAnalyticsEventRecord.geo_country_code,
                        func.count(SiteAnalyticsEventRecord.id),
                    )
                    .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                    .filter(SiteAnalyticsEventRecord.geo_country_code.isnot(None))
                    .group_by(SiteAnalyticsEventRecord.geo_country_code)
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all(),
                    "country_code",
                ),
                "top_cities": _geo_pairs(
                    base.with_entities(
                        SiteAnalyticsEventRecord.geo_city,
                        SiteAnalyticsEventRecord.geo_region,
                        SiteAnalyticsEventRecord.geo_country_code,
                        func.count(SiteAnalyticsEventRecord.id),
                    )
                    .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                    .filter(SiteAnalyticsEventRecord.geo_city.isnot(None))
                    .group_by(
                        SiteAnalyticsEventRecord.geo_city,
                        SiteAnalyticsEventRecord.geo_region,
                        SiteAnalyticsEventRecord.geo_country_code,
                    )
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all()
                ),
                "top_timezones": _pairs(
                    base.with_entities(
                        SiteAnalyticsEventRecord.geo_timezone,
                        func.count(SiteAnalyticsEventRecord.id),
                    )
                    .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                    .filter(SiteAnalyticsEventRecord.geo_timezone.isnot(None))
                    .group_by(SiteAnalyticsEventRecord.geo_timezone)
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all(),
                    "timezone",
                ),
                "top_networks": _pairs(
                    base.with_entities(SiteAnalyticsEventRecord.geo_org, func.count(SiteAnalyticsEventRecord.id))
                    .filter(SiteAnalyticsEventRecord.event_type == "pageview")
                    .filter(SiteAnalyticsEventRecord.geo_org.isnot(None))
                    .group_by(SiteAnalyticsEventRecord.geo_org)
                    .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
                    .limit(limit)
                    .all(),
                    "organization",
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
        "geo": {
            "country": row.geo_country,
            "country_code": row.geo_country_code,
            "region": row.geo_region,
            "city": row.geo_city,
            "timezone": row.geo_timezone,
            "continent": row.geo_continent,
            "organization": row.geo_org,
            "asn": row.geo_asn,
            "latitude": row.geo_latitude,
            "longitude": row.geo_longitude,
            "source": row.geo_source,
        },
    }


def _pairs(rows, key_name: str) -> list[dict[str, Any]]:
    return [{key_name: str(key or "unknown"), "count": int(count or 0)} for key, count in rows]


def _geo_pairs(rows) -> list[dict[str, Any]]:
    return [
        {
            "city": str(city or "unknown"),
            "region": region,
            "country_code": country_code,
            "count": int(count or 0),
        }
        for city, region, country_code, count in rows
    ]


def resolve_geo(headers: Mapping[str, str], ip_address: Optional[str]) -> dict[str, Any]:
    header_geo = _geo_from_headers(headers)
    lookup_geo = _geo_from_ip(ip_address)
    return {**header_geo, **lookup_geo} if lookup_geo else header_geo


def _geo_from_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    normalized = {str(key).lower(): value for key, value in headers.items() if value}
    country_code = (
        normalized.get("cf-ipcountry")
        or normalized.get("cloudfront-viewer-country")
        or normalized.get("x-vercel-ip-country")
        or normalized.get("x-country-code")
    )
    city = normalized.get("cloudfront-viewer-city") or normalized.get("x-vercel-ip-city")
    region = normalized.get("cloudfront-viewer-country-region") or normalized.get("x-vercel-ip-country-region")
    timezone = normalized.get("x-vercel-ip-timezone")
    latitude = normalized.get("cloudfront-viewer-latitude") or normalized.get("x-vercel-ip-latitude")
    longitude = normalized.get("cloudfront-viewer-longitude") or normalized.get("x-vercel-ip-longitude")
    result = {
        "country_code": country_code,
        "region": _unquote(region),
        "city": _unquote(city),
        "timezone": timezone,
        "latitude": latitude,
        "longitude": longitude,
    }
    cleaned = {key: value for key, value in result.items() if value}
    if cleaned:
        cleaned["source"] = "headers"
    return cleaned


_GEO_CACHE: dict[str, dict[str, Any]] = {}


def _geo_from_ip(ip_address: Optional[str]) -> dict[str, Any]:
    if not _geo_lookup_enabled() or not ip_address:
        return {}
    ip_address = ip_address.strip()
    if not _public_ip(ip_address):
        return {}
    if ip_address in _GEO_CACHE:
        return _GEO_CACHE[ip_address]
    provider = (os.getenv("SITE_ANALYTICS_GEO_PROVIDER") or "ipapi").strip().lower()
    if provider != "ipapi":
        return {}
    timeout = _geo_timeout()
    try:
        with urllib.request.urlopen(f"https://ipapi.co/{ip_address}/json/", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}
    if data.get("error"):
        return {}
    result = {
        "country": data.get("country_name"),
        "country_code": data.get("country_code"),
        "region": data.get("region"),
        "city": data.get("city"),
        "timezone": data.get("timezone"),
        "continent": data.get("continent_code"),
        "org": data.get("org"),
        "asn": data.get("asn"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "source": "ipapi",
    }
    cleaned = {key: value for key, value in result.items() if value}
    _GEO_CACHE[ip_address] = cleaned
    return cleaned


def _geo_lookup_enabled() -> bool:
    value = os.getenv("SITE_ANALYTICS_GEO_LOOKUP_ENABLED", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _geo_timeout() -> float:
    try:
        return max(0.1, min(float(os.getenv("SITE_ANALYTICS_GEO_TIMEOUT_SECONDS", "1.5")), 5.0))
    except ValueError:
        return 1.5


def _public_ip(value: str) -> bool:
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    )


def _unquote(value: Optional[str]) -> Optional[str]:
    return urllib.parse.unquote(value) if value else None


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


def _float_or_none(value: Optional[Any]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
