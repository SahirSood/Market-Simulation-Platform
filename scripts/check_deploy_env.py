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
    "NEWS_API_KEY",
    "SEC_USER_AGENT",
    "ARENA_API_KEY",
    "FRONTEND_URL",
    "PUBLIC_READ_ONLY_MODE",
    "ENGINE_NATIVE_REQUIRED",
    "API_SECURITY_HEADERS_ENABLED",
    "API_HSTS_ENABLED",
    "API_CORS_ALLOW_LOCALHOST",
    "API_RATE_LIMIT_ENABLED",
    "API_RATE_LIMIT_REQUESTS_PER_MINUTE",
    "API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE",
    "API_MAX_REQUEST_BODY_BYTES",
    "LLM_DAILY_SPEND_LIMIT_USD",
    "LLM_MONTHLY_SPEND_LIMIT_USD",
]
BACKEND_OPTIONAL_WARNINGS = {}
FRONTEND_REQUIRED = ["VITE_API_URL"]
FRONTEND_OPTIONAL_WARNINGS = {}
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


def _parse_float(value: str) -> float:
    return float(value.replace("_", "").replace(",", ""))


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def validate_env(env: dict[str, str], *, production: bool = False) -> tuple[list[str], list[str]]:
    """Return deployment warnings and errors without printing secret values."""
    errors: list[str] = []
    warnings: list[str] = []

    for key in BACKEND_REQUIRED + FRONTEND_REQUIRED:
        value = env.get(key, "").strip()
        if not value:
            errors.append(f"{key} is missing")
        elif _is_placeholder(value):
            errors.append(f"{key} still looks like a placeholder")

    for key, message in BACKEND_OPTIONAL_WARNINGS.items():
        value = env.get(key, "").strip()
        if not value or _is_placeholder(value):
            warnings.append(f"{key} is not set; {message}")

    if production:
        for key, message in FRONTEND_OPTIONAL_WARNINGS.items():
            value = env.get(key, "").strip()
            if not value or _is_placeholder(value):
                warnings.append(f"{key} is not set; {message}")

    openai_project = env.get("OPENAI_PROJECT_ID", "").strip() or env.get("OPENAI_PROJECT", "").strip()
    if not openai_project or _is_placeholder(openai_project):
        warnings.append("OPENAI_PROJECT_ID is not set; OpenAI requests will use the API key's default project")

    starting_cash = env.get("STARTING_CASH", "").strip()
    if starting_cash:
        try:
            parsed_cash = _parse_float(starting_cash)
        except ValueError:
            errors.append("STARTING_CASH must be a positive number")
        else:
            if parsed_cash <= 0:
                errors.append("STARTING_CASH must be a positive number")

    monthly_spend = env.get("LLM_MONTHLY_SPEND_LIMIT_USD", "").strip()
    daily_spend = env.get("LLM_DAILY_SPEND_LIMIT_USD", "").strip()
    parsed_monthly_spend = None
    if monthly_spend:
        try:
            parsed_monthly_spend = _parse_float(monthly_spend)
        except ValueError:
            errors.append("LLM_MONTHLY_SPEND_LIMIT_USD must be a positive number")
        else:
            if parsed_monthly_spend <= 0:
                errors.append("LLM_MONTHLY_SPEND_LIMIT_USD must be a positive number")
            if production and parsed_monthly_spend > 20:
                errors.append("LLM_MONTHLY_SPEND_LIMIT_USD must be 20 or less in production")
    if daily_spend:
        try:
            parsed_daily_spend = _parse_float(daily_spend)
        except ValueError:
            errors.append("LLM_DAILY_SPEND_LIMIT_USD must be a positive number")
        else:
            if parsed_daily_spend <= 0:
                errors.append("LLM_DAILY_SPEND_LIMIT_USD must be a positive number")
            if parsed_monthly_spend is not None and parsed_daily_spend > parsed_monthly_spend:
                errors.append("LLM_DAILY_SPEND_LIMIT_USD cannot exceed the monthly spend limit")

    if production:
        public_mode = env.get("PUBLIC_READ_ONLY_MODE", "").strip()
        if public_mode and not _truthy(public_mode):
            errors.append("PUBLIC_READ_ONLY_MODE must be true in production")
        sandbox_enabled = env.get("SANDBOX_ENABLED", "").strip()
        if sandbox_enabled and _truthy(sandbox_enabled):
            errors.append("SANDBOX_ENABLED must not be true in production")
        native_required = env.get("ENGINE_NATIVE_REQUIRED", "").strip()
        if native_required and not _truthy(native_required):
            errors.append("ENGINE_NATIVE_REQUIRED must be true in production")
        security_headers = env.get("API_SECURITY_HEADERS_ENABLED", "").strip()
        if security_headers and not _truthy(security_headers):
            errors.append("API_SECURITY_HEADERS_ENABLED must be true in production")
        hsts_enabled = env.get("API_HSTS_ENABLED", "").strip()
        if hsts_enabled and not _truthy(hsts_enabled):
            errors.append("API_HSTS_ENABLED must be true in production")
        localhost_cors = env.get("API_CORS_ALLOW_LOCALHOST", "").strip()
        if localhost_cors and _truthy(localhost_cors):
            errors.append("API_CORS_ALLOW_LOCALHOST must be false in production")
        rate_limit_enabled = env.get("API_RATE_LIMIT_ENABLED", "").strip()
        if rate_limit_enabled and not _truthy(rate_limit_enabled):
            errors.append("API_RATE_LIMIT_ENABLED must be true in production")
        site_analytics_enabled = env.get("VITE_SITE_ANALYTICS_ENABLED", "").strip()
        if site_analytics_enabled and not _truthy(site_analytics_enabled):
            errors.append("VITE_SITE_ANALYTICS_ENABLED must not be false in production")
        geo_lookup_enabled = env.get("SITE_ANALYTICS_GEO_LOOKUP_ENABLED", "").strip()
        if geo_lookup_enabled and not _truthy(geo_lookup_enabled):
            errors.append("SITE_ANALYTICS_GEO_LOOKUP_ENABLED must not be false in production")

    for key in (
        "API_RATE_LIMIT_REQUESTS_PER_MINUTE",
        "API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE",
        "API_MAX_REQUEST_BODY_BYTES",
    ):
        value = env.get(key, "").strip()
        if value:
            try:
                parsed_value = int(value.replace("_", "").replace(",", ""))
            except ValueError:
                errors.append(f"{key} must be a positive integer")
            else:
                if parsed_value <= 0:
                    errors.append(f"{key} must be a positive integer")

    for key in ("FRONTEND_URL", "VITE_API_URL"):
        value = env.get(key, "").strip()
        if value:
            _check_url(key, value, errors)
            if production and "localhost" in value:
                errors.append(f"{key} points at localhost in production mode")

    plausible_src = env.get("VITE_PLAUSIBLE_SRC", "").strip()
    if plausible_src:
        _check_url("VITE_PLAUSIBLE_SRC", plausible_src, errors)

    db_url = env.get("DATABASE_URL", "").strip()
    if db_url and not (db_url.startswith("postgresql://") or db_url.startswith("sqlite:///")):
        errors.append("DATABASE_URL must be postgresql:// or sqlite:///")

    return warnings, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deploy env readiness")
    parser.add_argument("--production", action="store_true", help="Reject localhost frontend/API URLs")
    args = parser.parse_args()

    env = _merged_env()
    warnings, errors = validate_env(env, production=args.production)

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
