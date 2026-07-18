import sys
from pathlib import Path
from types import SimpleNamespace

SIM_DIR = Path(__file__).resolve().parents[1]
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

from engine_adapter import EngineAdapter, is_native_engine_module


def test_invalid_engine_module_uses_stub_mode(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "engine", SimpleNamespace())

    adapter = EngineAdapter()

    assert adapter._engine is None
    order_id, fills = adapter.submit(
        ticker="AAPL",
        side="BUY",
        order_type="LIMIT",
        price=100.0,
        quantity=1,
        bot_id="test",
    )
    assert order_id == 1
    assert fills == []


def test_native_engine_contract_requires_binding_api():
    assert not is_native_engine_module(SimpleNamespace(OrderBook=object))

    assert is_native_engine_module(
        SimpleNamespace(
            OrderBook=object,
            Order=object,
            OrderSide=object,
            OrderType=object,
        )
    )
