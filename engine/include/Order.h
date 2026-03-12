#pragma once

#include <string>
#include <sstream>
#include <chrono>
#include <cstdint>

/** @brief Which side of the book an order belongs to. */
enum class OrderSide {
    BUY,
    SELL
};

/** @brief Execution style of the order. */
enum class OrderType {
    LIMIT,   ///< Rests in the book until matched or cancelled
    MARKET   ///< Fills immediately at best available price; never rests
};

/**
 * @brief A single order submitted to the matching engine.
 *
 * INTERVIEW NOTE: uint64_t for id/quantity avoids 32-bit overflow on busy exchanges.
 * double for price is fine in a simulator; production uses fixed-point integers
 * to eliminate floating-point rounding errors in financial calculations.
 */
struct Order {
    uint64_t  id;
    OrderSide side;
    OrderType type;
    double    price;
    uint64_t  quantity;
    std::chrono::system_clock::time_point timestamp;
    bool      is_filled = false;

    std::string toString() const {
        std::ostringstream oss;
        auto epoch_s = std::chrono::duration_cast<std::chrono::seconds>(
            timestamp.time_since_epoch()).count();
        oss << "Order[id=" << id
            << " side=" << (side == OrderSide::BUY ? "BUY" : "SELL")
            << " type=" << (type == OrderType::LIMIT ? "LIMIT" : "MARKET")
            << " price=" << price
            << " qty=" << quantity
            << " filled=" << (is_filled ? "yes" : "no")
            << " ts=" << epoch_s << "]";
        return oss.str();
    }
};
