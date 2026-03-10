#include <iostream>
#include "Order.h"
#include "OrderBook.h"

int main() {
    std::cout << "=== Day 3: OrderBook with sorted bid/ask containers ===\n";

    auto now = std::chrono::system_clock::now();

    // Construct the order book — default constructor is generated automatically
    // because our class has no user-defined constructor.
    OrderBook book;

    // --- Day 3 test: 5 BUY orders at specified prices ---
    // Prices: 189.00, 189.10, 188.90, 189.05, 188.95
    // After addOrder(), bids map should sort these HIGH → LOW automatically.
    book.addOrder({1, OrderSide::BUY,  OrderType::LIMIT, 189.00, 100, now, false});
    book.addOrder({2, OrderSide::BUY,  OrderType::LIMIT, 189.10,  50, now, false});
    book.addOrder({3, OrderSide::BUY,  OrderType::LIMIT, 188.90,  75, now, false});
    book.addOrder({4, OrderSide::BUY,  OrderType::LIMIT, 189.05,  30, now, false});
    book.addOrder({5, OrderSide::BUY,  OrderType::LIMIT, 188.95, 200, now, false});

    // --- Day 3 test: 5 SELL orders at specified prices ---
    // Prices: 189.20, 189.15, 189.30, 189.25, 189.10
    // After addOrder(), asks map should sort these LOW → HIGH automatically.
    book.addOrder({6,  OrderSide::SELL, OrderType::LIMIT, 189.20, 100, now, false});
    book.addOrder({7,  OrderSide::SELL, OrderType::LIMIT, 189.15,  80, now, false});
    book.addOrder({8,  OrderSide::SELL, OrderType::LIMIT, 189.30,  60, now, false});
    book.addOrder({9,  OrderSide::SELL, OrderType::LIMIT, 189.25,  40, now, false});
    book.addOrder({10, OrderSide::SELL, OrderType::LIMIT, 189.10, 150, now, false});

    // Expected output:
    //   Asks sorted LOW → HIGH:  189.10, 189.15, 189.20, 189.25, 189.30
    //   Bids sorted HIGH → LOW:  189.10, 189.05, 189.00, 188.95, 188.90
    //   Spread = 189.10 - 189.10 = 0.00  (crossed! — we'll handle this in Day 4's match())
    book.printBook();

    std::cout << "Best Bid: " << book.getBestBid() << "\n";
    std::cout << "Best Ask: " << book.getBestAsk() << "\n";

    return 0;
}
