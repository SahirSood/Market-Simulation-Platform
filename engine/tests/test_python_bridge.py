import engine
import time

# Test 1: basic order placement
ob = engine.OrderBook()
now = int(time.time() * 1e9)  # nanoseconds

ob.addOrder(engine.Order(1, engine.OrderSide.BUY,  engine.OrderType.LIMIT, 189.30, 100, now, False))
ob.addOrder(engine.Order(2, engine.OrderSide.SELL, engine.OrderType.LIMIT, 189.30,  60, now, False))
ob.match()

snap = ob.getSnapshot()
print(f"Spread: {snap.spread}")
print(f"Mid:    {snap.mid_price}")
print(f"Best bid: {ob.getBestBid()}")
print(f"Best ask: {ob.getBestAsk()}")

# Test 2: confirm trade executed
ob.printTradeLog()

# Test 3: snapshot bids/asks are Python lists
assert isinstance(snap.bids, list), "bids should be a Python list"
assert len(snap.bids) == 1,         "40 shares should remain on bid after partial fill"
assert snap.bids[0].total_quantity == 40, f"expected 40 remaining, got {snap.bids[0].total_quantity}"

# Test 4: trade count
assert ob.tradeCount() == 1, f"expected 1 trade, got {ob.tradeCount()}"

# Test 5: cancel an order
ob2 = engine.OrderBook()
ob2.addOrder(engine.Order(10, engine.OrderSide.BUY, engine.OrderType.LIMIT, 190.00, 50, now, False))
result = ob2.cancelOrder(10)
assert result == True,  "cancelOrder should return True for a live order"
result2 = ob2.cancelOrder(10)
assert result2 == False, "cancelOrder should return False for already-cancelled order"

print("All Python bridge tests passed.")
