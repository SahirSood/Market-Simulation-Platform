"""Validate deployment environment variables without printing secrets."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

BACKEND_REQUIRED = [
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "SEC_USER_AGENT",
    "ARENA_API_KEY",
    "FRONTEND_URL",
]
BACKEND_OPTIONAL = ["NEWS_API_KEY"]
FRONTEND_REQUIRED = ["VITE_API_URL"]
PLACEHOLDER_TOKENS = ("your_", "example", "local-demo-key")


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip(), value.strip())
    return values


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in PLACEHOLDER_TOKENS)


def _merged_env() -> dict[str, str]:
    values = _load_env_file(ROOT / ".env")
    values.update(_load_env_file(ROOT / "frontend" / ".env"))
    values.update({k: v for k, v in os.environ.items() if v})
    return values


def _check_url(name: str, value: str, errors: list[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{name} must be an absolute http(s) URL")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deploy env readiness")
    parser.add_argument("--production", action="store_true", help="Reject localhost frontend/API URLs")
    args = parser.parse_args()

    env = _merged_env()
    errors: list[str] = []
    warnings: list[str] = []

    for key in BACKEND_REQUIRED + FRONTEND_REQUIRED:
        value = env.get(key, "").strip()
        if not value:
            errors.append(f"{key} is missing")
        elif _is_placeholder(value):
            errors.append(f"{key} still looks like a placeholder")

    for key in BACKEND_OPTIONAL:
        value = env.get(key, "").strip()
        if not value or _is_placeholder(value):
            warnings.append(f"{key} is not set; live news will be disabled")

    for key in ("FRONTEND_URL", "VITE_API_URL"):
        value = env.get(key, "").strip()
        if value:
            _check_url(key, value, errors)
            if args.production and "localhost" in value:
                errors.append(f"{key} points at localhost in production mode")

    db_url = env.get("DATABASE_URL", "").strip()
    if db_url and not (db_url.startswith("postgresql://") or db_url.startswith("sqlite:///")):
        errors.append("DATABASE_URL must be postgresql:// or sqlite:///")

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Deployment environment check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
