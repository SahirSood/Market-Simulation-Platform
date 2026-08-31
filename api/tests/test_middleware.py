import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.middleware import setup_middleware


def _client():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/write")
    async def write(payload: dict | None = None):
        return {"ok": True, "payload": payload}

    setup_middleware(app)
    return TestClient(app)


def test_security_headers_are_added(monkeypatch):
    monkeypatch.delenv("API_HSTS_ENABLED", raising=False)
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "false")

    response = _client().get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_can_be_enabled(monkeypatch):
    monkeypatch.setenv("API_HSTS_ENABLED", "true")
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "false")

    response = _client().get("/health")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_cors_allows_configured_frontend_only(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://dashboard.example.test")
    monkeypatch.setenv("API_CORS_ALLOW_LOCALHOST", "false")
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "false")

    client = _client()
    allowed = client.options(
        "/health",
        headers={
            "Origin": "https://dashboard.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "https://dashboard.example.test"
    assert "access-control-allow-origin" not in blocked.headers


def test_cors_allows_loopback_frontend_in_local_mode(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.setenv("API_CORS_ALLOW_LOCALHOST", "true")
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "false")

    response = _client().options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_oversized_request_body_is_rejected(monkeypatch):
    monkeypatch.setenv("API_MAX_REQUEST_BODY_BYTES", "8")
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "false")

    response = _client().post("/write", json={"too": "large"})

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large"


def test_write_rate_limit_is_enforced_separately(monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("API_RATE_LIMIT_REQUESTS_PER_MINUTE", "10")
    monkeypatch.setenv("API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE", "1")
    monkeypatch.setenv("API_MAX_REQUEST_BODY_BYTES", "1000")

    client = _client()
    first = client.post("/write", json={"ok": True})
    second = client.post("/write", json={"ok": True})
    read = client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert read.status_code == 200
