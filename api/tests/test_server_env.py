import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api import state as app_state
from api.server import app, _readiness_payload, _required_env_vars, _restore_portfolios_from_reasoning_log, ready, root
from api.routers.sandbox import sandbox_start, sandbox_status
from api.dependencies import WritePrincipal
from portfolio import Portfolio
from fastapi import HTTPException
import pytest


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
    assert payload["ready"] == "/ready"
    assert payload["dashboard"] == "https://market-sim-frontend.onrender.com"


def test_api_app_mounts_site_analytics_routes() -> None:
    # FastAPI 0.141 stores included routers as internal wrapper entries, so
    # inspect the public OpenAPI contract rather than implementation details.
    paths = set(app.openapi().get("paths", {}))

    assert "/analytics/event" in paths
    assert "/analytics/summary" in paths


def test_readiness_allows_stub_engine_when_not_required(monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_NATIVE_REQUIRED", "false")
    monkeypatch.setenv("PUBLIC_READ_ONLY_MODE", "true")

    class Log:
        def count_decisions(self, **kwargs):
            return 3

    class Scheduler:
        def status(self):
            return {
                "running": True,
                "market_open": True,
                "spend_budget_exhausted": False,
            }

    class Rag:
        def count_documents(self):
            return 5

    app_state.init(SimpleNamespace(
        engine_adapter=SimpleNamespace(_engine=None),
        reasoning_log=Log(),
        scheduler=Scheduler(),
        rag_repository=Rag(),
    ))

    payload = _readiness_payload()

    assert payload["status"] == "ready"
    assert payload["checks"]["engine"]["status"] == "degraded"
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["rag"]["document_count"] == 5


def test_readiness_blocks_when_native_engine_required(monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_NATIVE_REQUIRED", "true")
    monkeypatch.setenv("PUBLIC_READ_ONLY_MODE", "true")

    class Log:
        def count_decisions(self, **kwargs):
            return 0

    app_state.init(SimpleNamespace(
        engine_adapter=SimpleNamespace(_engine=None),
        reasoning_log=Log(),
        scheduler=SimpleNamespace(status=lambda: {"running": True}),
        rag_repository=None,
    ))

    response = SimpleNamespace(status_code=200)
    payload = asyncio.run(ready(response))

    assert response.status_code == 503
    assert payload["status"] == "not_ready"
    assert "engine" in payload["blocking_checks"]


def test_readiness_does_not_expose_backend_exception_details(monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_NATIVE_REQUIRED", "false")
    monkeypatch.setenv("PUBLIC_READ_ONLY_MODE", "true")

    class Log:
        def count_decisions(self, **kwargs):
            raise RuntimeError("postgresql://user:secret@internal-db/marketsim")

    app_state.init(SimpleNamespace(
        engine_adapter=SimpleNamespace(_engine=None),
        reasoning_log=Log(),
        scheduler=SimpleNamespace(status=lambda: {"running": True}),
        rag_repository=None,
    ))

    payload = _readiness_payload()

    assert payload["status"] == "not_ready"
    assert payload["checks"]["database"]["message"] == "database check failed"
    assert "secret" not in str(payload)


def test_restore_portfolios_replays_persisted_fills() -> None:
    bot = SimpleNamespace(
        bot_id="contrarian-001-claude",
        portfolio=Portfolio(100_000),
    )

    class Log:
        def get_filled_decisions(self, bot_id):
            assert bot_id == "contrarian-001-claude"
            return [
                {
                    "id": 1,
                    "timestamp": None,
                    "action": "BUY",
                    "ticker": "AAPL",
                    "fill_qty_total": 50,
                    "fill_avg_price": 200.0,
                },
                {
                    "id": 2,
                    "timestamp": None,
                    "action": "SELL",
                    "ticker": "AAPL",
                    "fill_qty_total": 10,
                    "fill_avg_price": 210.0,
                },
            ]

    summary = _restore_portfolios_from_reasoning_log([bot], Log())

    snapshot = bot.portfolio.snapshot()
    assert summary == {"bots_restored": 1, "fills_replayed": 2}
    assert snapshot["positions"] == {"AAPL": 40}
    assert snapshot["cash"] == 92_100.0


def test_restore_portfolios_prefers_execution_fill_ledger() -> None:
    bot = SimpleNamespace(
        bot_id="contrarian-001-claude",
        portfolio=Portfolio(100_000),
    )

    class Log:
        def get_execution_fills(self, bot_id):
            assert bot_id == "contrarian-001-claude"
            return [
                {
                    "id": 10,
                    "execution_order_id": 5,
                    "engine_order_id": 100,
                    "timestamp": None,
                    "bot_id": bot_id,
                    "ticker": "MSFT",
                    "side": "BUY",
                    "quantity": 20,
                    "price": 300.0,
                    "notional": 6000.0,
                },
                {
                    "id": 11,
                    "execution_order_id": 6,
                    "engine_order_id": 101,
                    "timestamp": None,
                    "bot_id": bot_id,
                    "ticker": "MSFT",
                    "side": "SELL",
                    "quantity": 5,
                    "price": 310.0,
                    "notional": 1550.0,
                },
            ]

        def get_filled_decisions(self, bot_id):
            raise AssertionError("decision summary fallback should not be used")

    summary = _restore_portfolios_from_reasoning_log([bot], Log())

    snapshot = bot.portfolio.snapshot()
    assert summary == {"bots_restored": 1, "fills_replayed": 2}
    assert snapshot["positions"] == {"MSFT": 15}
    assert snapshot["cash"] == 95_550.0


def test_sandbox_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_ENABLED", raising=False)

    status = asyncio.run(sandbox_status())

    assert status.active is False
    assert status.message == "Sandbox is disabled"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(sandbox_start(WritePrincipal(actor="operator")))
    assert exc.value.status_code == 404
