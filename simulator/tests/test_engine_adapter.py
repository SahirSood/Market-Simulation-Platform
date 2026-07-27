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


def test_seed_liquidity_places_bid_and_ask_levels(monkeypatch):
    adapter = EngineAdapter()
    submitted = []

    def fake_submit(**kwargs):
        submitted.append(kwargs)
        return len(submitted), []

    monkeypatch.setattr(adapter, "submit", fake_submit)

    orders = adapter.seed_liquidity(
        ticker="AAPL",
        mid_price=100.0,
        levels=2,
        quantity=50,
        spread_pct=0.01,
    )

    assert orders == 4
    assert [row["side"] for row in submitted] == ["BUY", "SELL", "BUY", "SELL"]
    assert submitted[0]["price"] == 99.0
    assert submitted[1]["price"] == 101.0
    assert submitted[2]["price"] == 98.0
    assert submitted[3]["price"] == 102.0


def test_later_match_queues_fill_for_resting_bot():
    class FakeOrder:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeBook:
        def __init__(self):
            self.resting_sell = None
            self.trades = []

        def tradeCount(self):
            return len(self.trades)

        def addOrder(self, order):
            if order.side == "SELL":
                self.resting_sell = order
                return
            if self.resting_sell is not None:
                quantity = min(order.quantity, self.resting_sell.quantity)
                self.trades.append(SimpleNamespace(
                    buy_order_id=order.id,
                    sell_order_id=self.resting_sell.id,
                    quantity=quantity,
                    price=self.resting_sell.price,
                ))

        def getTrades(self, since_index):
            return self.trades[since_index:]

        def cancelOrder(self, order_id):
            return False

    adapter = EngineAdapter()
    adapter._engine = SimpleNamespace(
        OrderBook=FakeBook,
        Order=FakeOrder,
        OrderSide=SimpleNamespace(BUY="BUY", SELL="SELL"),
        OrderType=SimpleNamespace(LIMIT="LIMIT", MARKET="MARKET"),
    )

    resting_id, resting_fills = adapter.submit(
        ticker="AAPL",
        side="SELL",
        order_type="LIMIT",
        price=101.0,
        quantity=25,
        bot_id="bear-001",
    )
    incoming_id, incoming_fills = adapter.submit(
        ticker="AAPL",
        side="BUY",
        order_type="MARKET",
        price=102.0,
        quantity=25,
        bot_id="degen-001",
    )

    assert resting_fills == []
    assert [(fill.order_id, fill.side, fill.quantity, fill.price) for fill in incoming_fills] == [
        (incoming_id, "BUY", 25, 101.0)
    ]
    passive = adapter.drain_fills("bear-001")
    assert [(fill.order_id, fill.side, fill.quantity, fill.price) for fill in passive] == [
        (resting_id, "SELL", 25, 101.0)
    ]
    assert adapter.drain_fills("bear-001") == []
