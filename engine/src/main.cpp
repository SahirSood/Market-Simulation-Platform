#include <iostream>
#include <sstream>
#include <string>
#include <iomanip>
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


// Prints a BookSnapshot in a readable format.
static void printSnapshot(const BookSnapshot& snap) {
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "\n────────── SNAPSHOT ──────────\n";

    std::cout << "  ASKS:\n";
    if (snap.asks.empty()) std::cout << "    (empty)\n";
    for (const auto& lvl : snap.asks)
        std::cout << "    ASK  " << lvl.price << "  qty=" << lvl.total_quantity
                  << "  orders=" << lvl.order_count << "\n";

    std::cout << "  ─────────────────────────────\n";
    if (snap.spread > 0.0)
        std::cout << "  Spread: " << snap.spread << "   Mid: " << snap.mid_price << "\n";
    else
        std::cout << "  Spread: N/A\n";
    std::cout << "  ─────────────────────────────\n";

    std::cout << "  BIDS:\n";
    if (snap.bids.empty()) std::cout << "    (empty)\n";
    for (const auto& lvl : snap.bids)
        std::cout << "    BID  " << lvl.price << "  qty=" << lvl.total_quantity
                  << "  orders=" << lvl.order_count << "\n";

    std::cout << "──────────────────────────────\n\n";
}

// Parses and executes one line of user input.
// Accepted formats:
//   BUY <qty> <price>
//   SELL <qty> <price>
//   MARKET BUY <qty>
//   MARKET SELL <qty>
//   quit
static void runCLI() {
    std::cout << "Commands: BUY <qty> <price>  |  SELL <qty> <price>  "
                 "|  MARKET BUY <qty>  |  MARKET SELL <qty>  |  quit\n\n";

    OrderBook book;
    // IDs start at 100 to stay above the demo orders in day5()/day6().
    uint64_t next_id = 100;
    auto now = std::chrono::system_clock::now();

    std::string line;
    while (true) {
        std::cout << "> ";
        if (!std::getline(std::cin, line)) break;  // EOF (Ctrl-D / piped input)

        std::istringstream iss(line);
        std::string token;
        iss >> token;

        if (token == "quit" || token == "q") {
            std::cout << "Bye!\n";
            break;
        }

        Order order;
        order.id        = next_id++;
        order.is_filled = false;
        order.timestamp = std::chrono::system_clock::now();

        bool valid = true;

        if (token == "MARKET") {
            std::string side_str;
            uint64_t qty;
            if (!(iss >> side_str >> qty)) { valid = false; }
            else {
                order.type     = OrderType::MARKET;
                order.price    = 0.0;   // addOrder() will set sentinel price
                order.quantity = qty;
                if      (side_str == "BUY")  order.side = OrderSide::BUY;
                else if (side_str == "SELL") order.side = OrderSide::SELL;
                else valid = false;
            }
        } else if (token == "BUY" || token == "SELL") {
            uint64_t qty;
            double   price;
            if (!(iss >> qty >> price)) { valid = false; }
            else {
                order.type     = OrderType::LIMIT;
                order.quantity = qty;
                order.price    = price;
                order.side     = (token == "BUY") ? OrderSide::BUY : OrderSide::SELL;
            }
        } else {
            valid = false;
        }

        if (!valid) {
            std::cout << "  Unknown command. Try: BUY 100 189.30  or  MARKET SELL 50\n";
            continue;
        }

        book.addOrder(order);

        // For LIMIT orders, run the matcher explicitly.
        // (MARKET orders call match() inside addOrder already.)
        if (order.type == OrderType::LIMIT) {
            book.match();
        }

        printSnapshot(book.getSnapshot());
    }
}

int main() {
    day5();
    std::cout << "\n";
    day6();
    runCLI();
    return 0;
}
