#include "OrderBook.h"
#include <iostream>
#include <iomanip>    // for std::fixed, std::setprecision
#include <algorithm>  // for std::min
#include <limits>     // for std::numeric_limits (Day 5: market order sentinel prices)

// ─────────────────────────────────────────────
// addOrder
// ─────────────────────────────────────────────
void OrderBook::addOrder(Order order) {
    // (best_bid >= best_ask) is always satisfied, driving the order to consume
    // as much liquidity as exists.
    if (order.type == OrderType::MARKET) {
        if (order.side == OrderSide::BUY) {
            order.price = std::numeric_limits<double>::max();
        } else {
            order.price = 0.0;
        }
    }

    // Insert into the correct side of the book.
    // operator[] creates an empty deque at this price if it doesn't exist yet.
    if (order.side == OrderSide::BUY) {
        bids[order.price].push_back(order);
    } else {
        asks[order.price].push_back(order);
    }

    // Record (side, price) so cancelOrder() can find this order in O(1).
    // Market orders are registered too; they get removed by the cleanup below
    order_index[order.id] = {order.side, order.price};

    // INTERVIEW NOTE: "Walking the book" and slippage.
    // A market order sweeps price levels one by one until filled:
    //   asks: 189.10×50, 189.20×30, 189.30×40 — MARKET BUY 200:
    //     fill 50 @ 189.10, then 30 @ 189.20, then 40 @ 189.30 → 120 filled.
    //   80 remaining, asks exhausted → cancel remainder.
    // Each successive fill is at a worse price than the last. That degradation
    // in average fill price versus the initial best ask is "slippage" — the
    // market impact of trading a size that exceeds available liquidity.
    //
    // INTERVIEW NOTE: Why don't we leave the partial remainder resting?
    // A market order has no price constraint.
    if (order.type == OrderType::MARKET) {
        match();

        // Clean up any unfilled remainder sitting at the sentinel price.
        // Erasing the entire level is safe: no real limit order would ever
        // have price == DBL_MAX or price == 0.0, so only our market order is there.
        if (order.side == OrderSide::BUY) {
            auto it = bids.find(std::numeric_limits<double>::max());
            if (it != bids.end()) {
                // Remove each remaining order's ID from the index before erasing the level.
                for (const auto& o : it->second) order_index.erase(o.id);
                bids.erase(it);
            }
        } else {
            auto it = asks.find(0.0);
            if (it != asks.end()) {
                for (const auto& o : it->second) order_index.erase(o.id);
                asks.erase(it);
            }
        }
    }
}

// ─────────────────────────────────────────────
// getBestBid / getBestAsk
// ─────────────────────────────────────────────
double OrderBook::getBestBid() const {
    if (bids.empty()) return 0.0;
    // std::greater comparator → begin() = highest price = best bid.
    return bids.begin()->first;
}

double OrderBook::getBestAsk() const {
    if (asks.empty()) return 0.0;
    // Default ascending sort → begin() = lowest price = best ask.
    return asks.begin()->first;
}

// ─────────────────────────────────────────────
// printBook
// ─────────────────────────────────────────────
void OrderBook::printBook() const {
    std::cout << "\n========== ORDER BOOK ==========\n";
    std::cout << std::fixed << std::setprecision(2);

    std::cout << "  ASKS (lowest price = best ask):\n";
    int levels_shown = 0;
    for (const auto& [price, deq] : asks) {
        uint64_t total_qty = 0;
        // Day 6: deque supports range-for directly — no need to copy and drain.
        for (const auto& o : deq) total_qty += o.quantity;
        std::cout << "    ASK  " << price << "  qty=" << total_qty << "\n";
        if (++levels_shown >= 5) break;
    }

    std::cout << "  --------------------------------\n";
    std::cout << "       SPREAD = ";
    if (!bids.empty() && !asks.empty()) {
        std::cout << (getBestAsk() - getBestBid()) << "\n";
    } else {
        std::cout << "N/A\n";
    }
    std::cout << "  --------------------------------\n";

    std::cout << "  BIDS (highest price = best bid):\n";
    levels_shown = 0;
    for (const auto& [price, deq] : bids) {
        uint64_t total_qty = 0;
        for (const auto& o : deq) total_qty += o.quantity;
        std::cout << "    BID  " << price << "  qty=" << total_qty << "\n";
        if (++levels_shown >= 5) break;
    }

    std::cout << "=================================\n\n";
}

// ─────────────────────────────────────────────
// match
// ─────────────────────────────────────────────
void OrderBook::match() {
    while (!bids.empty() && !asks.empty() &&
           bids.begin()->first >= asks.begin()->first)
    {
        // References into the front of each best-price deque.
        // We modify .quantity through these references — no copies.
        Order& bid_order = bids.begin()->second.front();
        Order& ask_order = asks.begin()->second.front();

        uint64_t fill_qty = std::min(bid_order.quantity, ask_order.quantity);

        // INTERVIEW NOTE: Trade price = ask price (passive side sets the price).
        // The resting ask arrived first and quoted a price; the aggressor (buyer)
        // crossed the spread and accepted that price. This is price-time priority.
        double trade_price = asks.begin()->first;

        Trade t;
        t.trade_id      = next_trade_id++;
        t.buy_order_id  = bid_order.id;
        t.sell_order_id = ask_order.id;
        t.price         = trade_price;
        t.quantity      = fill_qty;
        t.timestamp     = std::chrono::system_clock::now();
        trade_log.push_back(t);

        bid_order.quantity -= fill_qty;
        ask_order.quantity -= fill_qty;

        // ── DAY 6: save ID before pop_front() invalidates the reference ───────
        if (ask_order.quantity == 0) {
            uint64_t ask_id = ask_order.id;
            asks.begin()->second.pop_front();
            order_index.erase(ask_id);   // remove from shadow index
            if (asks.begin()->second.empty()) asks.erase(asks.begin());
        }

        if (bid_order.quantity == 0) {
            uint64_t bid_id = bid_order.id;
            bids.begin()->second.pop_front();
            order_index.erase(bid_id);   // remove from shadow index
            if (bids.begin()->second.empty()) bids.erase(bids.begin());
        }
    }
}

// ─────────────────────────────────────────────
// cancelOrder  (Day 6)
// ─────────────────────────────────────────────
bool OrderBook::cancelOrder(uint64_t order_id) {
    // Step 1: O(1) index lookup — find (side, price) for this order ID.
    auto idx_it = order_index.find(order_id);
    if (idx_it == order_index.end()) {
        // Not in index → already filled, already cancelled, or never existed.
        // INTERVIEW NOTE: On a real exchange this is the graceful handling of the
        // cancel-vs-fill race: if the order filled in the same microsecond the
        // cancel arrived, we return false and the trader will see a fill report.
        return false;
    }

    auto [side, price] = idx_it->second;  // structured binding (C++17)

    // Step 2: Find the price-level deque in the correct side of the book.
    // Step 3: Scan the (typically tiny) deque for the matching order ID and erase it.
    if (side == OrderSide::BUY) {
        auto map_it = bids.find(price);
        if (map_it != bids.end()) {
            auto& deq = map_it->second;
            for (auto it = deq.begin(); it != deq.end(); ++it) {
                if (it->id == order_id) {
                    deq.erase(it);
                    if (deq.empty()) bids.erase(map_it);  // clean up phantom level
                    order_index.erase(idx_it);
                    return true;
                }
            }
        }
    } else {
        auto map_it = asks.find(price);
        if (map_it != asks.end()) {
            auto& deq = map_it->second;
            for (auto it = deq.begin(); it != deq.end(); ++it) {
                if (it->id == order_id) {
                    deq.erase(it);
                    if (deq.empty()) asks.erase(map_it);
                    order_index.erase(idx_it);
                    return true;
                }
            }
        }
    }

    // Index said the order exists but we couldn't find it in the book — stale entry.
    // Clean up and return false rather than crashing.
    order_index.erase(idx_it);
    return false;
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
