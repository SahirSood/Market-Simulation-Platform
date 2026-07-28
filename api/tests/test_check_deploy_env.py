import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.check_deploy_env import validate_env


def _valid_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql://user:password@host:5432/marketsim",
        "ANTHROPIC_API_KEY": "anthropic_live_key",
        "OPENAI_API_KEY": "openai_live_key",
        "OPENAI_PROJECT_ID": "proj_live_project",
        "NEWS_API_KEY": "news_live_key",
        "SEC_USER_AGENT": "MarketSimulationPlatform/1.0 ops@company.test",
        "ARENA_API_KEY": "strong-write-key",
        "STARTING_CASH": "100,000",
        "FRONTEND_URL": "https://dashboard.company.test",
        "VITE_API_URL": "https://api.company.test",
        "VITE_PLAUSIBLE_DOMAIN": "dashboard.company.test",
        "VITE_PLAUSIBLE_SRC": "https://plausible.io/js/script.outbound-links.js",
        "VITE_SITE_ANALYTICS_ENABLED": "true",
        "PUBLIC_READ_ONLY_MODE": "true",
        "SANDBOX_ENABLED": "false",
        "ENGINE_NATIVE_REQUIRED": "true",
        "API_SECURITY_HEADERS_ENABLED": "true",
        "API_HSTS_ENABLED": "true",
        "API_CORS_ALLOW_LOCALHOST": "false",
        "API_RATE_LIMIT_ENABLED": "true",
        "API_RATE_LIMIT_REQUESTS_PER_MINUTE": "240",
        "API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE": "30",
        "API_MAX_REQUEST_BODY_BYTES": "1048576",
        "LLM_DAILY_SPEND_LIMIT_USD": "1",
        "LLM_MONTHLY_SPEND_LIMIT_USD": "20",
    }


def test_validate_env_accepts_complete_production_env() -> None:
    warnings, errors = validate_env(_valid_env(), production=True)

    assert warnings == []
    assert errors == []


def test_validate_env_warns_for_optional_openai_project() -> None:
    env = _valid_env()
    env.pop("OPENAI_PROJECT_ID")

    warnings, errors = validate_env(env, production=True)

    assert errors == []
    assert any("OPENAI_PROJECT_ID is not set" in warning for warning in warnings)


def test_validate_env_rejects_openai_only_production_deploy() -> None:
    env = _valid_env()
    env["ANTHROPIC_API_KEY"] = ""

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "ANTHROPIC_API_KEY is missing" in errors


def test_validate_env_rejects_invalid_starting_cash() -> None:
    env = _valid_env()
    env["STARTING_CASH"] = "not-a-number"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "STARTING_CASH must be a positive number" in errors


def test_validate_env_rejects_localhost_in_production() -> None:
    env = _valid_env()
    env["FRONTEND_URL"] = "http://localhost:5173"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "FRONTEND_URL points at localhost in production mode" in errors


def test_validate_env_rejects_non_view_only_production() -> None:
    env = _valid_env()
    env["PUBLIC_READ_ONLY_MODE"] = "false"
    env["SANDBOX_ENABLED"] = "true"
    env["ENGINE_NATIVE_REQUIRED"] = "false"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "PUBLIC_READ_ONLY_MODE must be true in production" in errors
    assert "SANDBOX_ENABLED must not be true in production" in errors
    assert "ENGINE_NATIVE_REQUIRED must be true in production" in errors


def test_validate_env_rejects_disabled_api_hardening_in_production() -> None:
    env = _valid_env()
    env["API_SECURITY_HEADERS_ENABLED"] = "false"
    env["API_HSTS_ENABLED"] = "false"
    env["API_CORS_ALLOW_LOCALHOST"] = "true"
    env["API_RATE_LIMIT_ENABLED"] = "false"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "API_SECURITY_HEADERS_ENABLED must be true in production" in errors
    assert "API_HSTS_ENABLED must be true in production" in errors
    assert "API_CORS_ALLOW_LOCALHOST must be false in production" in errors
    assert "API_RATE_LIMIT_ENABLED must be true in production" in errors


def test_validate_env_rejects_disabled_site_analytics_in_production() -> None:
    env = _valid_env()
    env["VITE_SITE_ANALYTICS_ENABLED"] = "false"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "VITE_SITE_ANALYTICS_ENABLED must not be false in production" in errors


def test_validate_env_rejects_invalid_api_limit_values() -> None:
    env = _valid_env()
    env["API_RATE_LIMIT_REQUESTS_PER_MINUTE"] = "0"
    env["API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE"] = "not-int"
    env["API_MAX_REQUEST_BODY_BYTES"] = "-1"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "API_RATE_LIMIT_REQUESTS_PER_MINUTE must be a positive integer" in errors
    assert "API_WRITE_RATE_LIMIT_REQUESTS_PER_MINUTE must be a positive integer" in errors
    assert "API_MAX_REQUEST_BODY_BYTES must be a positive integer" in errors


def test_validate_env_rejects_monthly_budget_above_cap() -> None:
    env = _valid_env()
    env["LLM_MONTHLY_SPEND_LIMIT_USD"] = "25"

    warnings, errors = validate_env(env, production=True)

    assert warnings == []
    assert "LLM_MONTHLY_SPEND_LIMIT_USD must be 20 or less in production" in errors
