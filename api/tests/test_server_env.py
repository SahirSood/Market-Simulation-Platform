import sys
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.server import _required_env_vars, root


def test_api_boot_does_not_require_provider_keys_for_live_demo() -> None:
    assert _required_env_vars(offline_mode=False) == ["DATABASE_URL"]


def test_api_boot_does_not_require_provider_keys_for_offline_mode() -> None:
    assert _required_env_vars(offline_mode=True) == ["DATABASE_URL"]


def test_api_root_identifies_dashboard_and_docs(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://market-sim-frontend.onrender.com")

    payload = asyncio.run(root())

    assert payload["status"] == "ok"
    assert payload["docs"] == "/docs"
    assert payload["health"] == "/health"
    assert payload["dashboard"] == "https://market-sim-frontend.onrender.com"
