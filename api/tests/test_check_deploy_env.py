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


def test_validate_env_allows_openai_only_deploy() -> None:
    env = _valid_env()
    env["ANTHROPIC_API_KEY"] = ""

    warnings, errors = validate_env(env, production=True)

    assert errors == []
    assert any("Claude bots will fall back to HOLD" in warning for warning in warnings)


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
