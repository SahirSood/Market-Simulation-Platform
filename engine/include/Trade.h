#pragma once

#include <string>
#include <sstream>
#include <chrono>
#include <cstdint>

// A Trade is created when two orders match — one buy and one sell.
// It is an immutable record of what happened: who traded, at what price, for how much.
struct Trade {
    uint64_t trade_id;       // Unique ID for this trade execution
    uint64_t buy_order_id;   // Which buy order was involved
    uint64_t sell_order_id;  // Which sell order was involved
    double   price;          // Price at which the trade executed
    uint64_t quantity;       // Number of shares/contracts that changed hands
    std::chrono::system_clock::time_point timestamp;

    std::string toString() const {
        std::ostringstream oss;

        auto epoch_seconds = std::chrono::duration_cast<std::chrono::seconds>(
            timestamp.time_since_epoch()
        ).count();

        oss << "Trade["
            << "trade_id=" << trade_id
            << " buy_order=" << buy_order_id
            << " sell_order=" << sell_order_id
            << " price=" << price
            << " qty=" << quantity
            << " ts=" << epoch_seconds << "]";

        return oss.str();
    }
};
