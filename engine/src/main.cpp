#include <iostream>
#include "Order.h"
#include "OrderBook.h"

// ═══════════════════════════════════════════════════════════
// DAY 5 — Market Orders
// ═══════════════════════════════════════════════════════════
void day5() {
    std::cout << "=== Day 5: Market Orders ===\n\n";

    OrderBook book;
    auto now = std::chrono::system_clock::now();

    // Build the ask side: 50 + 30 + 40 = 120 shares total liquidity.
    book.addOrder({1, OrderSide::SELL, OrderType::LIMIT, 189.10, 50, now, false});
    book.addOrder({2, OrderSide::SELL, OrderType::LIMIT, 189.20, 30, now, false});
    book.addOrder({3, OrderSide::SELL, OrderType::LIMIT, 189.30, 40, now, false});

    std::cout << "Book before market order (120 shares of ask liquidity):\n";
    book.printBook();

    // MARKET BUY 200 — more than the 120 available.
    // addOrder() sets price = DBL_MAX, calls match(), then erases the 80-share remainder.
    //
    // match() walk:
    //   iter 1: DBL_MAX >= 189.10 → fill min(200,50)=50  → SELL#1 done, remainder=150
    //   iter 2: DBL_MAX >= 189.20 → fill min(150,30)=30  → SELL#2 done, remainder=120
    //   iter 3: DBL_MAX >= 189.30 → fill min(120,40)=40  → SELL#3 done, remainder=80
    //   iter 4: asks empty → loop exits
    // Cleanup: bids.find(DBL_MAX) → erase the 80-share remnant. Book is empty.
    book.addOrder({4, OrderSide::BUY, OrderType::MARKET, 0.0, 200, now, false});

    std::cout << "After MARKET BUY 200 vs 120 liquidity (expect 3 trades, empty book):\n";
    book.printBook();
    book.printTradeLog();
}

// ═══════════════════════════════════════════════════════════
// DAY 6 — Order Cancellation
// ═══════════════════════════════════════════════════════════
void day6() {
    std::cout << "=== Day 6: Order Cancellation ===\n\n";

    OrderBook book;
    auto now = std::chrono::system_clock::now();

    // Add 5 resting orders — no crossing yet, so no trades.
    book.addOrder({1, OrderSide::BUY,  OrderType::LIMIT, 190.00, 100, now, false});
    book.addOrder({2, OrderSide::BUY,  OrderType::LIMIT, 189.00,  50, now, false});
    book.addOrder({3, OrderSide::SELL, OrderType::LIMIT, 191.00, 100, now, false}); // ← cancel target
    book.addOrder({4, OrderSide::SELL, OrderType::LIMIT, 192.00,  50, now, false});
    book.addOrder({5, OrderSide::BUY,  OrderType::LIMIT, 188.00,  75, now, false});

    std::cout << "Book with 5 orders (before cancel):\n";
    book.printBook();

    // ── Cancel order 3 ───────────────────────────────────────────────────────
    // order_index lookup: id=3 → (SELL, 191.00)
    // asks.find(191.00) → deque with one order → erase it → erase empty level
    // order_index.erase(3)
    bool cancelled = book.cancelOrder(3);
    std::cout << "cancelOrder(3) returned: " << (cancelled ? "true" : "false")
              << "  (expected: true)\n\n";

    // ── Cancel non-existent order ─────────────────────────────────────────────
    // INTERVIEW NOTE: cancelOrder(999) hits order_index.find(999) == end() → return false.
    // On a real exchange this is how stale/duplicate cancel requests are handled gracefully.
    bool bad_cancel = book.cancelOrder(999);
    std::cout << "cancelOrder(999) returned: " << (bad_cancel ? "true" : "false")
              << "  (expected: false)\n\n";

    std::cout << "Book after cancelling order 3 (SELL@191 should be gone):\n";
    book.printBook();

    // ── Add a matching SELL that crosses BUY@190 ─────────────────────────────
    // BUY#1 @ 190.00 is still live. A new SELL @ 190.00 should match against it.
    // Order 3 (SELL@191) is gone — it plays NO role here.
    book.addOrder({6, OrderSide::SELL, OrderType::LIMIT, 190.00, 100, now, false});
    book.match();

    std::cout << "After adding SELL 100 @ 190.00 and matching:\n";
    book.printBook();
    book.printTradeLog();

    // Expected:
    //   1 trade: buy_order=1, sell_order=6, 100 @ 190.00
    //   order 3 never appears in trade log
    //   remaining book: BID 189.00×50, BID 188.00×75, ASK 192.00×50
}

int main() {
    day5();
    std::cout << "\n";
    day6();
    return 0;
}
