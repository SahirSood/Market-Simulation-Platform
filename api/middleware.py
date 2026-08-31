"""API middleware for CORS, security headers, body limits, and rate limits."""
from __future__ import annotations

import os
import threading
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

_TRUE_VALUES = {"1", "true", "yes", "on"}
_DEFAULT_LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=_bool_env("API_CORS_ALLOW_CREDENTIALS", False),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Actor", "X-Request-ID"],
    )

    limiter = _InMemoryRateLimiter(
        read_limit_per_minute=_int_env("API_RATE_LIMIT_REQUESTS_PER_MINUTE", 240),
        write_limit_per_minute=_int_env("API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE", 60),
    )

    @app.middleware("http")
    async def public_api_hardening(request: Request, call_next):
        max_body_bytes = _int_env("API_MAX_REQUEST_BODY_BYTES", 1_048_576)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_body_bytes:
                    return JSONResponse(
                        {"detail": "Request body too large"},
                        status_code=413,
                    )
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length header"}, status_code=400)

        if _bool_env("API_RATE_LIMIT_ENABLED", True):
            scope = "write" if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} else "read"
            allowed, retry_after = limiter.check(_client_key(request), scope)
            if not allowed:
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)
        if _bool_env("API_SECURITY_HEADERS_ENABLED", True):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=()",
            )
            if _bool_env("API_HSTS_ENABLED", False):
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
        return response


class _InMemoryRateLimiter:
    def __init__(self, read_limit_per_minute: int, write_limit_per_minute: int):
        self._read_limit = max(0, int(read_limit_per_minute))
        self._write_limit = max(0, int(write_limit_per_minute))
        self._window_seconds = 60.0
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, client_key: str, scope: str) -> tuple[bool, int]:
        limit = self._write_limit if scope == "write" else self._read_limit
        if limit <= 0:
            return True, 0

        now = time.monotonic()
        bucket_key = (client_key, scope)
        with self._lock:
            self._prune(now)
            window_start, count = self._buckets.get(bucket_key, (now, 0))
            elapsed = now - window_start
            if elapsed >= self._window_seconds:
                self._buckets[bucket_key] = (now, 1)
                return True, 0
            if count >= limit:
                retry_after = max(1, int(self._window_seconds - elapsed))
                return False, retry_after
            self._buckets[bucket_key] = (window_start, count + 1)
            return True, 0

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, (window_start, _) in self._buckets.items()
            if now - window_start >= self._window_seconds * 2
        ]
        for key in expired:
            self._buckets.pop(key, None)


def _allowed_origins() -> list[str]:
    origins = []
    origins.extend(_split_csv(os.getenv("API_CORS_ORIGINS", "")))
    origins.extend(_split_csv(os.getenv("FRONTEND_URL", "")))
    if _bool_env("API_CORS_ALLOW_LOCALHOST", True):
        origins.extend(_DEFAULT_LOCAL_ORIGINS)
    return list(dict.fromkeys(origin.rstrip("/") for origin in origins if origin))


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip() or "unknown"
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "unknown"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in _TRUE_VALUES


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.replace("_", "").replace(",", ""))
    except ValueError:
        return default
