"""First-party deployed-site analytics endpoints."""
from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import RedirectResponse

from api import state as app_state
from api.dependencies import WritePrincipal, require_write_auth
from site_analytics import resolve_geo

router = APIRouter()

_REDIRECT_TARGETS = {
    "github": {
        "url": "https://github.com/SahirSood/Market-Simulation-Platform",
        "label": "github",
    },
    "demo": {
        "url": "https://drive.google.com/file/d/1QgwnKADxQlL0hUa9pGXkoYMembmDNSGX/view?usp=drivesdk",
        "label": "demo-video",
    },
}


class SiteAnalyticsEventRequest(BaseModel):
    event_type: Literal["pageview", "outbound_click"] = "pageview"
    path: str = Field(default="/", max_length=512)
    url: str | None = Field(default=None, max_length=4096)
    title: str | None = Field(default=None, max_length=256)
    referrer: str | None = Field(default=None, max_length=4096)
    utm_source: str | None = Field(default=None, max_length=128)
    utm_medium: str | None = Field(default=None, max_length=128)
    utm_campaign: str | None = Field(default=None, max_length=128)
    target_url: str | None = Field(default=None, max_length=4096)
    session_id: str | None = Field(default=None, max_length=128)
    metadata: dict = Field(default_factory=dict)


@router.post("/analytics/event")
async def record_site_analytics_event(request: Request):
    """Record one bounded public dashboard analytics event."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid analytics payload")
    try:
        payload = SiteAnalyticsEventRequest.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors())

    store = _require_store()
    ip_address = _client_ip(request)
    geo = await asyncio.to_thread(resolve_geo, request.headers, ip_address)
    event_id = await asyncio.to_thread(
        store.record_event,
        event_type=payload.event_type,
        path=payload.path,
        url=payload.url,
        title=payload.title,
        referrer=payload.referrer,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        target_url=payload.target_url,
        session_id=payload.session_id,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        geo=geo,
        metadata=payload.metadata,
    )
    return {"ok": True, "event_id": event_id}


@router.get("/analytics/summary")
async def get_site_analytics_summary(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    principal: WritePrincipal = Depends(require_write_auth),
):
    """Protected summary of deployed-site views, sources, and outbound clicks."""
    store = _require_store()
    return {
        **await asyncio.to_thread(store.summary, days=days, limit=limit),
        "principal": {
            "actor": principal.actor,
            "auth_method": principal.auth_method,
        },
    }


@router.get("/go/{target}")
@router.get("/go/{target}/{source}")
async def redirect_and_track(
    target: str,
    request: Request,
    source: str | None = None,
):
    """Record an allowlisted outbound click, then immediately redirect."""
    target_key = target.lower().strip()
    destination = _REDIRECT_TARGETS.get(target_key)
    if destination is None:
        raise HTTPException(404, "Tracked redirect target not found")

    source_key = _clean_source(source) or "direct"
    campaign = "market_sim_showcase"
    path = request.url.path
    await _record_redirect_click(
        request=request,
        path=path,
        source=source_key,
        campaign=campaign,
        target_url=destination["url"],
        target_label=destination["label"],
    )
    return RedirectResponse(destination["url"], status_code=302)


def _require_store():
    store = getattr(app_state.get(), "site_analytics", None)
    if store is None:
        raise HTTPException(404, "Site analytics store is not configured")
    return store


async def _record_redirect_click(
    *,
    request: Request,
    path: str,
    source: str,
    campaign: str,
    target_url: str,
    target_label: str,
) -> None:
    store = _require_store()
    ip_address = _client_ip(request)
    geo = await asyncio.to_thread(resolve_geo, request.headers, ip_address)
    await asyncio.to_thread(
        store.record_event,
        event_type="outbound_click",
        path=path,
        url=str(request.url),
        referrer=request.headers.get("referer"),
        utm_source=source,
        utm_medium="redirect",
        utm_campaign=campaign,
        target_url=target_url,
        session_id=None,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        geo=geo,
        metadata={"redirect_target": target_label},
    )


def _clean_source(source: str | None) -> str | None:
    if not source:
        return None
    cleaned = "".join(ch for ch in source.lower().strip() if ch.isalnum() or ch in ("-", "_"))
    return cleaned[:64] or None


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip() or None
    client = getattr(request, "client", None)
    return getattr(client, "host", None)
