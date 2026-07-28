import asyncio
import json
import os
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(ROOT, "simulator")
for path in (ROOT, SIM_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from api import state as app_state
from api.dependencies import WritePrincipal
from api.routers import analytics
from api.routers.analytics import get_site_analytics_summary
from site_analytics import SiteAnalyticsStore, resolve_geo


def test_site_analytics_records_sources_paths_and_outbound_clicks(tmp_path):
    store = SiteAnalyticsStore(f"sqlite:///{tmp_path / 'analytics.db'}")
    store.record_event(
        event_type="pageview",
        path="/",
        url="https://market-sim-frontend.onrender.com/?utm_source=github&utm_medium=repo&utm_campaign=launch",
        referrer="https://github.com/SahirSood/Market-Simulation-Platform",
        utm_source="github",
        utm_medium="repo",
        utm_campaign="launch",
        session_id="session-1",
        ip_address="203.0.113.10",
        user_agent="pytest",
        geo={
            "country": "Canada",
            "country_code": "CA",
            "region": "British Columbia",
            "city": "Vancouver",
            "timezone": "America/Vancouver",
            "org": "Example ISP",
            "latitude": 49.2827,
            "longitude": -123.1207,
            "source": "ipapi",
        },
    )
    store.record_event(
        event_type="outbound_click",
        path="/",
        target_url="https://github.com/SahirSood/Market-Simulation-Platform",
        session_id="session-1",
        ip_address="203.0.113.10",
        user_agent="pytest",
    )

    summary = store.summary()

    assert summary["pageviews"] == 1
    assert summary["outbound_clicks"] == 1
    assert summary["unique_sessions"] == 1
    assert summary["unique_visitors"] == 1
    assert summary["top_sources"][0] == {"source": "github", "count": 1}
    assert summary["top_paths"][0] == {"path": "/", "count": 1}
    assert summary["top_countries"][0] == {"country_code": "CA", "count": 1}
    assert summary["top_cities"][0] == {
        "city": "Vancouver",
        "region": "British Columbia",
        "country_code": "CA",
        "count": 1,
    }
    assert summary["top_timezones"][0] == {"timezone": "America/Vancouver", "count": 1}
    assert summary["top_networks"][0] == {"organization": "Example ISP", "count": 1}
    assert summary["top_outbound_targets"][0] == {
        "target_domain": "github.com",
        "count": 1,
    }
    assert "ip_hash" not in summary["recent_events"][0]
    assert summary["recent_events"][0]["geo"]["country_code"] in (None, "CA")


def test_site_analytics_summary_endpoint_requires_operator_context(tmp_path):
    store = SiteAnalyticsStore(f"sqlite:///{tmp_path / 'analytics.db'}")
    store.record_event(event_type="pageview", path="/bots", session_id="session-2")
    app_state.init(SimpleNamespace(site_analytics=store))

    result = asyncio.run(
        get_site_analytics_summary(
            days=30,
            limit=10,
            principal=WritePrincipal(actor="operator"),
        )
    )

    assert result["pageviews"] == 1
    assert result["principal"]["actor"] == "operator"


def test_site_analytics_api_accepts_beacon_payload_and_protects_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("ARENA_API_KEY", "analytics-secret")
    store = SiteAnalyticsStore(f"sqlite:///{tmp_path / 'analytics.db'}")
    app_state.init(SimpleNamespace(site_analytics=store))
    app = FastAPI()
    app.include_router(analytics.router)
    client = TestClient(app)

    response = client.post(
        "/analytics/event",
        content=json.dumps(
            {
                "event_type": "pageview",
                "path": "/",
                "url": "https://market-sim-frontend.onrender.com/?utm_source=github",
                "utm_source": "github",
                "session_id": "session-3",
            }
        ),
        headers={"content-type": "text/plain"},
    )
    summary = client.get(
        "/analytics/summary",
        headers={"X-API-Key": "analytics-secret", "X-Actor": "operator"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert summary.status_code == 200
    assert summary.json()["pageviews"] == 1
    assert summary.json()["top_sources"][0] == {"source": "github", "count": 1}


def test_tracked_redirect_records_click_and_stays_allowlisted(tmp_path, monkeypatch):
    monkeypatch.setenv("ARENA_API_KEY", "analytics-secret")
    store = SiteAnalyticsStore(f"sqlite:///{tmp_path / 'analytics.db'}")
    app_state.init(SimpleNamespace(site_analytics=store))
    app = FastAPI()
    app.include_router(analytics.router)
    client = TestClient(app)

    response = client.get(
        "/go/github/linkedin",
        follow_redirects=False,
        headers={"referer": "https://www.linkedin.com/feed/update/demo"},
    )
    blocked = client.get("/go/evil/linkedin", follow_redirects=False)
    summary = client.get(
        "/analytics/summary",
        headers={"X-API-Key": "analytics-secret", "X-Actor": "operator"},
    ).json()

    assert response.status_code == 302
    assert response.headers["location"] == "https://github.com/SahirSood/Market-Simulation-Platform"
    assert blocked.status_code == 404
    assert summary["outbound_clicks"] == 1
    assert summary["top_outbound_targets"][0] == {"target_domain": "github.com", "count": 1}
    assert summary["recent_events"][0]["source"] == "linkedin"
    assert summary["recent_events"][0]["utm_campaign"] == "market_sim_showcase"


def test_site_analytics_geo_uses_proxy_headers_without_raw_ip_lookup(monkeypatch):
    monkeypatch.delenv("SITE_ANALYTICS_GEO_LOOKUP_ENABLED", raising=False)

    geo = resolve_geo(
        {
            "CF-IPCountry": "US",
            "CloudFront-Viewer-City": "San%20Francisco",
            "CloudFront-Viewer-Country-Region": "California",
            "CloudFront-Viewer-Latitude": "37.7749",
            "CloudFront-Viewer-Longitude": "-122.4194",
        },
        "8.8.8.8",
    )

    assert geo == {
        "country_code": "US",
        "region": "California",
        "city": "San Francisco",
        "latitude": "37.7749",
        "longitude": "-122.4194",
        "source": "headers",
    }
