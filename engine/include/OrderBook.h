#pragma once

#include <map>
#include <queue>
#include <vector>
#include <functional>   // for std::greater
#include "Order.h"
#include "Trade.h"

// internal state (bids, asks, trade_log) that should NOT be directly readable
// or writable from outside. 
class OrderBook {
private:
    // --- BID SIDE ---
    // It keeps keys sorted at all times. Insert, lookup, and erase are all O(log n).
    //
    // Key   = double (price level, e.g. 189.10)
    // Value = std::queue<Order> (all orders resting at this price, in arrival order)
    // This is what we want for bids — the best (highest) bid is at the front.
    std::map<double, std::queue<Order>, std::greater<double>> bids;

    // --- ASK SIDE ---
    // This is correct for asks — the best (lowest) ask is at the front.
    std::map<double, std::queue<Order>> asks;

    // All trades that have been matched in this session.
    // std::vector is a dynamic array: O(1) push_back, O(n) iteration.
    std::vector<Trade> trade_log;

    // Counter used to assign unique IDs to each new trade.
    uint64_t next_trade_id = 1;

public:
    // Adds an order to the correct side of the book.
    // Takes Order by value (a copy) because we may modify quantity later during matching.
    void addOrder(Order order);

    // Prints the top 5 price levels of each side to stdout.
    // 'const' = this method does not change any member variables.
    void printBook() const;

    // Returns the highest buy price in the book (top of bid side).
    // Returns 0.0 if the bid side is empty.
    double getBestBid() const;

    // Returns the lowest sell price in the book (top of ask side).
    // Returns 0.0 if the ask side is empty.
    double getBestAsk() const;

    // Runs the matching algorithm: pairs bids and asks while best bid >= best ask.
    // Creates Trade objects and stores them in trade_log.
    void match();

    // Prints all trades in trade_log to stdout.
    void printTradeLog() const;
};
