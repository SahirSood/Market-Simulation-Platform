"""CORS + rate limiting middleware setup."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _SLOWAPI_AVAILABLE = True
except ImportError:
    _SLOWAPI_AVAILABLE = False

# Allowed frontend origins — add your Vercel domain here later
_ORIGINS = [
    "http://localhost:3000",    # Docker/nginx frontend
    "http://localhost:5173",    # Vite dev server
    os.getenv("FRONTEND_URL", ""),
]


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in _ORIGINS if o],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    if _SLOWAPI_AVAILABLE:
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
