#include "OrderBook.h"
#include <iostream>
#include <iomanip>    // for std::fixed, std::setprecision
#include <algorithm>  // for std::min
#include <limits>     // for std::numeric_limits (Day 5: market order sentinel prices)

// ─────────────────────────────────────────────
// addOrder
// ─────────────────────────────────────────────
void OrderBook::addOrder(Order order) {
    // ── DAY 5: Market order sentinel price trick ──────────────────────────────
    // We reuse the existing match() loop without modification by assigning a
    // sentinel price that will always satisfy the crossing condition.
    //
    // match() loops while: bids.begin()->first >= asks.begin()->first
    // The market order will keep matching until asks run out or it's fully filled.
    // Same logic applies to 0.0 for a market sell (0.0 <= any bid price).
    if (order.type == OrderType::MARKET) {
        if (order.side == OrderSide::BUY) {
            order.price = std::numeric_limits<double>::max();
        } else {
            order.price = 0.0;
        }
    }

    if (order.side == OrderSide::BUY) {
        // operator[] on a std::map: if the key (price) doesn't exist yet,
        // it creates a new empty queue at that price automatically.
        bids[order.price].push(order);
    } else {
        asks[order.price].push(order);
    }

    // A market order says "fill me NOW at any price". If liquidity runs out, the
    // unfilled portion has no economic meaning — there is no price the trader was
    // unwilling to pay, and no reason to wait for the next seller.
    //
    // "Walking the book" / slippage
    // If asks are: 189.10×50, 189.20×30, 189.30×40 and we send MARKET BUY 200:
    //   - Fill 50 @ 189.10  (best ask)
    //   - Fill 30 @ 189.20  (next level — worse price)
    //   - Fill 40 @ 189.30  (next level — even worse price)
    //   - 80 remaining, asks exhausted → cancel remainder
    // The average fill price is worse than the initial best ask. That gap is
    // "slippage" — the cost of size vs. available liquidity.
    if (order.type == OrderType::MARKET) {
        match();  // sweeps the book until filled or asks/bids exhausted

        // Clean up any unfilled remainder at the sentinel price.
        // Erasing the whole level is safe: no real limit order would ever sit
        if (order.side == OrderSide::BUY) {
            auto it = bids.find(std::numeric_limits<double>::max());
            if (it != bids.end()) bids.erase(it);
        } else {
            auto it = asks.find(0.0);
            if (it != asks.end()) asks.erase(it);
        }
    }
}

// ─────────────────────────────────────────────
// getBestBid / getBestAsk
// ─────────────────────────────────────────────
double OrderBook::getBestBid() const {
    if (bids.empty()) return 0.0;
    // begin() on a std::map points to the first element in sorted order.
    // For bids (sorted with std::greater), that's the HIGHEST price.
    // ->first gives us the key (price). ->second would give us the queue.
    return bids.begin()->first;
}

double OrderBook::getBestAsk() const {
    if (asks.empty()) return 0.0;
    // For asks (sorted ascending by default), begin() = LOWEST price.
    return asks.begin()->first;
}

// ─────────────────────────────────────────────
// printBook
// ─────────────────────────────────────────────
void OrderBook::printBook() const {
    std::cout << "\n========== ORDER BOOK ==========\n";
    std::cout << std::fixed << std::setprecision(2);  // print prices with 2 decimal places

    // --- ASKS (displayed top-down, worst ask first so the book looks like a real terminal) ---
    std::cout << "  ASKS (lowest price = best ask):\n";
    int levels_shown = 0;
    for (const auto& [price, queue] : asks) {
        // Sum quantities of all orders at this price level
        uint64_t total_qty = 0;
        std::queue<Order> temp = queue;   // copy the queue so we don't destroy it
        while (!temp.empty()) {
            total_qty += temp.front().quantity;
            temp.pop();
        }

        std::cout << "    ASK  " << price << "  qty=" << total_qty << "\n";
        if (++levels_shown >= 5) break;  // show at most top 5 levels
    }

    std::cout << "  --------------------------------\n";
    std::cout << "       SPREAD = ";
    if (!bids.empty() && !asks.empty()) {
        std::cout << (getBestAsk() - getBestBid()) << "\n";
    } else {
        std::cout << "N/A\n";
    }
    std::cout << "  --------------------------------\n";

    // --- BIDS ---
    std::cout << "  BIDS (highest price = best bid):\n";
    levels_shown = 0;
    for (const auto& [price, queue] : bids) {
        uint64_t total_qty = 0;
        std::queue<Order> temp = queue;
        while (!temp.empty()) {
            total_qty += temp.front().quantity;
            temp.pop();
        }

        std::cout << "    BID  " << price << "  qty=" << total_qty << "\n";
        if (++levels_shown >= 5) break;
    }

    std::cout << "=================================\n\n";
}

// ─────────────────────────────────────────────
// match
// ─────────────────────────────────────────────
void OrderBook::match() {
    // Keep matching as long as:
    //   1. There are orders on both sides
    //   2. The best bid price >= the best ask price (the spread is "crossed" or zero)
    while (!bids.empty() && !asks.empty() &&
           bids.begin()->first >= asks.begin()->first)
    {
        // Get a REFERENCE to the front order at the best bid and best ask.
        // We use references so that when we modify .quantity, we modify the
        // actual order in the queue — not a copy.
        Order& bid_order = bids.begin()->second.front();
        Order& ask_order = asks.begin()->second.front();

        // Fill quantity = the smaller of the two orders.
        // If BUY 100 meets SELL 60: fill 60, leave 40 remaining on the BUY.
        // INTERVIEW NOTE: std::min requires both arguments to be the same type.
        // Both quantities are uint64_t so this is fine.
        uint64_t fill_qty = std::min(bid_order.quantity, ask_order.quantity);

        // INTERVIEW NOTE: Trade price = ask price, NOT bid price.
        // The resting order (ask) set the price first.
        // The aggressor (buyer who crossed the spread) agrees to pay that price.
        // This is "price-time priority": the passive side determines the price.
        double trade_price = asks.begin()->first;

        // Record the trade
        Trade t;
        t.trade_id     = next_trade_id++;
        t.buy_order_id  = bid_order.id;
        t.sell_order_id = ask_order.id;
        t.price         = trade_price;
        t.quantity      = fill_qty;
        t.timestamp     = std::chrono::system_clock::now();
        trade_log.push_back(t);

        // Reduce quantities on both orders
        bid_order.quantity -= fill_qty;
        ask_order.quantity -= fill_qty;

        // If the ask is fully filled, remove it from the queue.
        // If that was the only order at this price level, erase the price level entirely.
        if (ask_order.quantity == 0) {
            asks.begin()->second.pop();             // remove front of queue
            if (asks.begin()->second.empty()) {
                asks.erase(asks.begin());           // erase empty price level
                // INTERVIEW NOTE: Erasing empty levels is important for correctness.
                // If we leave an empty queue in the map, getBestAsk() would return
                // a stale price with no actual orders behind it — a "phantom level".
            }
        }

        // Same for the bid side
        if (bid_order.quantity == 0) {
            bids.begin()->second.pop();
            if (bids.begin()->second.empty()) {
                bids.erase(bids.begin());
            }
        }
    }
}

// ─────────────────────────────────────────────
// printTradeLog
// ─────────────────────────────────────────────
void OrderBook::printTradeLog() const {
    std::cout << "\n========== TRADE LOG ==========\n";
    if (trade_log.empty()) {
        std::cout << "  (no trades executed)\n";
    } else {
        for (const Trade& t : trade_log) {
            std::cout << "  " << t.toString() << "\n";
        }
    }
    std::cout << "================================\n\n";
}
