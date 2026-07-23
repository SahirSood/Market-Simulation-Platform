#pragma once

#include <string>
#include <sstream>
#include <chrono>
#include <cstdint>

/**
 * @brief Immutable record of a matched trade between one buy and one sell order.
 *
 * Created inside match() whenever best_bid >= best_ask. Never modified after creation.
 */
struct Trade {
    uint64_t trade_id;
    uint64_t buy_order_id;
    uint64_t sell_order_id;
    double   price;     ///< Passive resting side sets the execution price
    uint64_t quantity;
    std::chrono::system_clock::time_point timestamp;

    std::string toString() const {
        std::ostringstream oss;
        auto epoch_s = std::chrono::duration_cast<std::chrono::seconds>(
            timestamp.time_since_epoch()).count();
        oss << "Trade[trade_id=" << trade_id
            << " buy_order=" << buy_order_id
            << " sell_order=" << sell_order_id
            << " price=" << price
            << " qty=" << quantity
            << " ts=" << epoch_s << "]";
        return oss.str();
    }
};
