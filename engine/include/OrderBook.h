#pragma once

#include <map>
#include <deque>          // Day 6: replaces std::queue — deque supports iteration + erase for cancel
#include <vector>
#include <unordered_map>  // Day 6: O(1) order lookup by ID for cancellation
#include <functional>     // for std::greater
#include "Order.h"
#include "Trade.h"

class OrderBook {
private:
    // --- BID SIDE ---
    // Key   = price level (double)
    // Value = deque of Orders at that price, in arrival order (FIFO = price-time priority)
    // std::greater<double> → highest bid price at begin() (best bid)
    //
    // INTERVIEW NOTE: We changed from std::queue to std::deque (Day 6).
    // std::queue is a restricted adapter: push/pop/front only — no iteration, no erase.
    // std::deque exposes the same front()/pop_front() interface (match() barely changes)
    // but also supports iterator-based erase(), which cancelOrder() requires.
    std::map<double, std::deque<Order>, std::greater<double>> bids;

    // --- ASK SIDE ---
    // Default ascending sort → lowest ask at begin() (best ask)
    std::map<double, std::deque<Order>> asks;

    // All trades matched in this session.
    std::vector<Trade> trade_log;

    // Monotonically increasing counter for unique trade IDs.
    uint64_t next_trade_id = 1;

    // "shadow book" ─────────────────────────────
    // Maps order_id → (side, price_level).
    //
    // Given an order ID we can immediately find which half of the book it's on
    // and which price-level deque to look in, without scanning the entire book.
    //
    // INTERVIEW NOTE: Why unordered_map instead of map?
    //   map lookup  = O(log n)
    //   unordered_map lookup = O(1) average (hash table)
    //
    // What is a "shadow book"?
    // The order_index is a second view of the same data as bids/asks, but
    // indexed by ID rather than price. It "shadows" the book and must be kept
    // in sync: every addOrder() inserts into the index, every match() fill and
    // every cancelOrder() removes from it.
    std::unordered_map<uint64_t, std::pair<OrderSide, double>> order_index;

public:
    // Adds an order. LIMIT orders rest; MARKET orders match immediately and
    void addOrder(Order order);

    // Runs the price-time-priority matching loop.
    void match();

    // Cancels the order with the given ID.
    // Returns true if found and removed, false if the ID is unknown (already
    //
    // INTERVIEW NOTE: On a real exchange, the race condition between a cancel
    // request and a fill executing in the matching engine is a real problem.
    // If the order fills in the same microsecond a cancel arrives, the cancel
    // silently returns false — the trader sees a fill they thought they cancelled.
    // This is handled with acknowledgement messages and order state machines.
    bool cancelOrder(uint64_t order_id);

    void printBook() const;
    double getBestBid() const;
    double getBestAsk() const;
    void printTradeLog() const;
};
