import time

import pytest

engine = pytest.importorskip("engine", reason="C++ pybind11 engine module is not built")


def test_python_bridge_matches_and_cancels_orders():
    order_book = engine.OrderBook()
    now = int(time.time() * 1e9)

    order_book.addOrder(
        engine.Order(1, engine.OrderSide.BUY, engine.OrderType.LIMIT, 189.30, 100, now, False)
    )
    order_book.addOrder(
        engine.Order(2, engine.OrderSide.SELL, engine.OrderType.LIMIT, 189.30, 60, now, False)
    )
    order_book.match()

    snapshot = order_book.getSnapshot()
    assert isinstance(snapshot.bids, list)
    assert len(snapshot.bids) == 1
    assert snapshot.bids[0].total_quantity == 40
    assert order_book.tradeCount() == 1

    second_book = engine.OrderBook()
    second_book.addOrder(
        engine.Order(10, engine.OrderSide.BUY, engine.OrderType.LIMIT, 190.00, 50, now, False)
    )
    assert second_book.cancelOrder(10) is True
    assert second_book.cancelOrder(10) is False
