#pragma once

#include <map>
#include <deque>
#include <vector>
#include <unordered_map>
#include <functional>
#include <chrono>
#include "Order.h"
#include "Trade.h"

/** @brief Aggregated view of one price level: total shares and order count. */
struct PriceLevel {
    double   price;
    uint64_t total_quantity;
    int      order_count;
};

/**
 * @brief Point-in-time snapshot of the top 5 bid and ask levels.
 *
 * External consumers (bots, GUIs, risk engines) use snapshots rather than
 * accessing book internals directly, keeping the interface stable.
 */
struct BookSnapshot {
    std::vector<PriceLevel> bids;  ///< Top 5, highest price first
    std::vector<PriceLevel> asks;  ///< Top 5, lowest price first
    double spread;
    double mid_price;
    std::chrono::system_clock::time_point timestamp;
};

/**
 * @brief Central limit order book with price-time priority matching.
 *
 * Bids are sorted descending (highest = best), asks ascending (lowest = best).
 * Within each price level, orders are FIFO. A shadow index enables O(1) cancellation.
 *
 * INTERVIEW NOTE: std::map gives O(log n) access. Production engines use flat arrays
 * indexed by price tick for O(1), pushing throughput from ~1M to 10M+ orders/sec.
 */
class OrderBook {
private:
    // Highest bid at begin() via std::greater; deque (not queue) to support erase for cancellation.
    std::map<double, std::deque<Order>, std::greater<double>> bids;
    std::map<double, std::deque<Order>> asks;

    std::vector<Trade> trade_log;
    uint64_t next_trade_id = 1;

    // Shadow index: order_id -> (side, price). Keeps cancellation O(1) without scanning the book.
    // Must stay in sync with bids/asks on every addOrder, match, and cancelOrder.
    std::unordered_map<uint64_t, std::pair<OrderSide, double>> order_index;

public:
    /** @brief Add an order. MARKET orders match immediately; LIMIT orders rest until matched. */
    void addOrder(Order order);

    /** @brief Run the price-time-priority matching loop until no crossing orders remain. */
    void match();

    /**
     * @brief Cancel the order with the given ID.
     * @return true if found and removed; false if already filled, cancelled, or unknown.
     */
    bool cancelOrder(uint64_t order_id);

    /** @brief Return a snapshot of the top 5 bid/ask levels with spread and mid price. */
    BookSnapshot getSnapshot() const;

    void   printBook()     const;
    void   printTradeLog() const;
    double getBestBid()    const;
    double getBestAsk()    const;
    size_t tradeCount()    const { return trade_log.size(); }

    /** @brief Return all trades since the given index (default: all trades). */
    std::vector<Trade> getTrades(size_t since_index = 0) const {
        if (since_index >= trade_log.size()) return {};
        return std::vector<Trade>(trade_log.begin() + since_index, trade_log.end());
    }
};
