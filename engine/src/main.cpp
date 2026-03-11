#include <iostream>
#include "Order.h"
#include "OrderBook.h"

int main() {
    std::cout << "=== Day 5: Market Orders ===\n\n";

    OrderBook book;
    auto now = std::chrono::system_clock::now();

    // ── Step 1: Build the ask side ────────────────────────────────────────────
    // Total available liquidity = 50 + 30 + 40 = 120 shares
    //
    // After these three addOrder calls the book looks like:
    //   ASK  189.10  qty=50   (best ask — cheapest)
    //   ASK  189.20  qty=30
    //   ASK  189.30  qty=40
    book.addOrder({1, OrderSide::SELL, OrderType::LIMIT, 189.10, 50, now, false});
    book.addOrder({2, OrderSide::SELL, OrderType::LIMIT, 189.20, 30, now, false});
    book.addOrder({3, OrderSide::SELL, OrderType::LIMIT, 189.30, 40, now, false});

    std::cout << "Book before market order (120 shares of liquidity on ask side):\n";
    book.printBook();

    // ── Step 2: MARKET BUY for 200 (more than the 120 available) ─────────────
    //
    // Inside addOrder(), the price is set to DBL_MAX, then match() is called.
    // match() will walk the book:
    //   Iteration 1: best bid = DBL_MAX >= best ask 189.10 → fill min(200,50)=50
    //                SELL order 1 fully filled (removed). Remainder = 150.
    //   Iteration 2: best bid = DBL_MAX >= best ask 189.20 → fill min(150,30)=30
    //                SELL order 2 fully filled (removed). Remainder = 120.
    //   Iteration 3: best bid = DBL_MAX >= best ask 189.30 → fill min(120,40)=40
    //                SELL order 3 fully filled (removed). Remainder = 80.
    //   Iteration 4: asks is now EMPTY → loop exits.
    //
    // Back in addOrder(): bids.find(DBL_MAX) finds the 80-share remainder → erased.
    // The market order is gone. No resting order at a phantom price.
    book.addOrder({4, OrderSide::BUY, OrderType::MARKET, 0.0 /*ignored*/, 200, now, false});

    // ── Expected results ──────────────────────────────────────────────────────
    //   Trade log: 3 trades
    //     Trade 1: 50 @ 189.10   (order 4 vs order 1)
    //     Trade 2: 30 @ 189.20   (order 4 vs order 2)
    //     Trade 3: 40 @ 189.30   (order 4 vs order 3)
    //
    //   Book: both sides empty (no bids were ever added as limits; asks all filled)
    std::cout << "After MARKET BUY 200 against 120 available (expect 3 trades, book empty):\n";
    book.printBook();
    book.printTradeLog();

    return 0;
}
