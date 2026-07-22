import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.server import _required_env_vars, _restore_portfolios_from_reasoning_log, root
from portfolio import Portfolio


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
