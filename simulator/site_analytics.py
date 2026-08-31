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

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, create_engine, func, inspect, or_, text
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
            **({} if database_url.startswith("sqlite") else {
                "pool_size": 5,
                "max_overflow": 2,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
            }),
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
            rows = base.order_by(SiteAnalyticsEventRecord.timestamp.asc()).all()
            events = _normalized_event_entries(rows)
            visit_events = [event for event in events if event["event_type"] == "pageview"]
            route_events = [event for event in events if _is_route_event(event)]
            outbound_events = [event for event in events if event["event_type"] == "outbound_click"]
            return {
                "window_days": days,
                "total_events": len(events),
                "pageviews": len(visit_events),
                "route_views": len([event for event in events if event["event_type"] == "route_view"]),
                "outbound_clicks": len(outbound_events),
                "unique_sessions": _unique_attr_count(events, "session_id"),
                "unique_visitors": _unique_attr_count(events, "ip_hash"),
                "by_day": _top_event_pairs(visit_events, lambda event: event["row"].timestamp.date().isoformat(), days, "date"),
                "top_sources": _top_event_pairs(visit_events, lambda event: event["row"].source, limit, "source"),
                "top_paths": _top_event_pairs(route_events, lambda event: event["row"].path, limit, "path"),
                "top_countries": _top_event_pairs(
                    [event for event in visit_events if event["row"].geo_country_code],
                    lambda event: event["row"].geo_country_code,
                    limit,
                    "country_code",
                ),
                "top_cities": _top_geo_events(visit_events, limit),
                "top_timezones": _top_event_pairs(
                    [event for event in visit_events if event["row"].geo_timezone],
                    lambda event: event["row"].geo_timezone,
                    limit,
                    "timezone",
                ),
                "top_networks": _top_event_pairs(
                    [event for event in visit_events if event["row"].geo_org],
                    lambda event: event["row"].geo_org,
                    limit,
                    "organization",
                ),
                "top_outbound_targets": _top_event_pairs(
                    outbound_events,
                    lambda event: event["row"].target_domain,
                    limit,
                    "target_domain",
                ),
                "tracked_surfaces": {
                    "site": _surface_summary_from_events(
                        [event for event in events if _is_route_event(event)],
                        limit=limit,
                        count_name="views",
                    ),
                    "demo": _surface_summary_from_events(
                        [
                            event
                            for event in outbound_events
                            if event["row"].target_domain == "drive.google.com"
                            or (event["row"].target_url and "drive.google.com" in event["row"].target_url)
                        ],
                        limit=limit,
                        count_name="clicks",
                    ),
                    "github": _surface_summary_from_events(
                        [
                            event
                            for event in outbound_events
                            if event["row"].target_domain == "github.com"
                            or (event["row"].target_url and "github.com" in event["row"].target_url)
                        ],
                        limit=limit,
                        count_name="clicks",
                    ),
                },
                "visits": _visit_summaries(events, limit),
                "recent_events": [_event_entry_to_dict(event) for event in sorted(events, key=lambda item: item["row"].timestamp, reverse=True)[:limit]],
            }


def _normalized_event_entries(rows: list[SiteAnalyticsEventRecord]) -> list[dict[str, Any]]:
    seen_visits: set[str] = set()
    events: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: item.timestamp):
        event_type = row.event_type
        if event_type == "pageview":
            key = _event_visit_key({"row": row, "event_type": event_type})
            if key and key in seen_visits:
                event_type = "route_view"
            elif key:
                seen_visits.add(key)
        events.append({"row": row, "event_type": event_type})
    return events


def _event_visit_key(event: dict[str, Any]) -> str | None:
    row = event["row"]
    if row.session_id:
        return f"session:{row.session_id}"
    if row.ip_hash:
        return f"visitor:{row.ip_hash}:{row.timestamp.date().isoformat()}"
    return None


def _is_route_event(event: dict[str, Any]) -> bool:
    return event["event_type"] in {"pageview", "route_view"}


def _unique_attr_count(events: list[dict[str, Any]], attr: str) -> int:
    return len({getattr(event["row"], attr) for event in events if getattr(event["row"], attr)})


def _top_event_pairs(
    events: list[dict[str, Any]],
    key_fn,
    limit: int,
    key_name: str,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for event in events:
        key = key_fn(event) or "unknown"
        counts[str(key)] = counts.get(str(key), 0) + 1
    return [
        {key_name: key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _top_geo_events(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str | None, str | None], int] = {}
    for event in events:
        row = event["row"]
        if not row.geo_city:
            continue
        key = (row.geo_city, row.geo_region, row.geo_country_code)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"city": city, "region": region, "country_code": country_code, "count": count}
        for (city, region, country_code), count in sorted(
            counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]
    ]


def _surface_summary_from_events(
    events: list[dict[str, Any]],
    *,
    limit: int,
    count_name: str,
) -> dict[str, Any]:
    counted_events = (
        [event for event in events if event["event_type"] == "pageview"]
        if count_name == "views"
        else _deduped_actor_events(events)
    )
    return {
        count_name: len(counted_events),
        "events": len(events),
        "unique_sessions": _unique_attr_count(events, "session_id"),
        "unique_visitors": _unique_attr_count(events, "ip_hash"),
        "top_sources": _top_event_pairs(counted_events, lambda event: event["row"].source, limit, "source"),
        "top_countries": _top_event_pairs(
            [event for event in counted_events if event["row"].geo_country_code],
            lambda event: event["row"].geo_country_code,
            limit,
            "country_code",
        ),
        "top_cities": _top_geo_events(counted_events, limit),
        "top_timezones": _top_event_pairs(
            [event for event in counted_events if event["row"].geo_timezone],
            lambda event: event["row"].geo_timezone,
            limit,
            "timezone",
        ),
        "top_networks": _top_event_pairs(
            [event for event in counted_events if event["row"].geo_org],
            lambda event: event["row"].geo_org,
            limit,
            "organization",
        ),
        "recent_events": [
            _event_entry_to_dict(event)
            for event in sorted(events, key=lambda item: item["row"].timestamp, reverse=True)[:limit]
        ],
    }


def _deduped_actor_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda item: item["row"].timestamp):
        key = _event_visit_key(event) or f"event:{event['row'].id}"
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def _visit_summaries(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    visits: dict[str, dict[str, Any]] = {}
    for event in sorted(events, key=lambda item: item["row"].timestamp):
        row = event["row"]
        key = _event_visit_key(event) or f"event:{row.id}"
        if key not in visits:
            visits[key] = {
                "id": key,
                "site": "market",
                "started_at": row.timestamp,
                "last_seen_at": row.timestamp,
                "source": row.source,
                "entry_path": row.path,
                "geo": _event_geo(row),
                "events": [],
            }
        visit = visits[key]
        visit["last_seen_at"] = row.timestamp
        if event["event_type"] == "pageview":
            visit["started_at"] = row.timestamp
            visit["source"] = row.source
            visit["entry_path"] = row.path
            visit["geo"] = _event_geo(row)
        visit["events"].append(_event_entry_to_dict(event))

    summaries = []
    for visit in visits.values():
        visit_events = visit["events"]
        summaries.append(
            {
                **visit,
                "action_count": len(visit_events),
                "route_count": len([event for event in visit_events if event["event_type"] in {"pageview", "route_view"}]),
                "outbound_count": len([event for event in visit_events if event["event_type"] == "outbound_click"]),
            }
        )
    return sorted(summaries, key=lambda item: item["started_at"], reverse=True)[:limit]


def _event_entry_to_dict(event: dict[str, Any]) -> dict[str, Any]:
    result = _event_to_dict(event["row"])
    result["event_type"] = event["event_type"]
    return result


def _event_geo(row: SiteAnalyticsEventRecord) -> dict[str, Any]:
    return {
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
    }


def _surface_summary(base, *, limit: int, count_name: str) -> dict[str, Any]:
    event_count = base.with_entities(func.count(SiteAnalyticsEventRecord.id)).scalar() or 0
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
        count_name: int(event_count),
        "events": int(event_count),
        "unique_sessions": int(unique_sessions),
        "unique_visitors": int(unique_visitors),
        "top_sources": _pairs(
            base.with_entities(SiteAnalyticsEventRecord.source, func.count(SiteAnalyticsEventRecord.id))
            .group_by(SiteAnalyticsEventRecord.source)
            .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
            .limit(limit)
            .all(),
            "source",
        ),
        "top_countries": _pairs(
            base.with_entities(SiteAnalyticsEventRecord.geo_country_code, func.count(SiteAnalyticsEventRecord.id))
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
            base.with_entities(SiteAnalyticsEventRecord.geo_timezone, func.count(SiteAnalyticsEventRecord.id))
            .filter(SiteAnalyticsEventRecord.geo_timezone.isnot(None))
            .group_by(SiteAnalyticsEventRecord.geo_timezone)
            .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
            .limit(limit)
            .all(),
            "timezone",
        ),
        "top_networks": _pairs(
            base.with_entities(SiteAnalyticsEventRecord.geo_org, func.count(SiteAnalyticsEventRecord.id))
            .filter(SiteAnalyticsEventRecord.geo_org.isnot(None))
            .group_by(SiteAnalyticsEventRecord.geo_org)
            .order_by(func.count(SiteAnalyticsEventRecord.id).desc())
            .limit(limit)
            .all(),
            "organization",
        ),
        "recent_events": [
            _event_to_dict(row)
            for row in base.order_by(SiteAnalyticsEventRecord.timestamp.desc()).limit(limit).all()
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
        "geo": _event_geo(row),
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
