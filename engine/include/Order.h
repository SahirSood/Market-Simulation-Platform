#pragma once
// #pragma once tells the compiler: "only include this file once per compilation unit,
// even if it's #included multiple times in different headers."
// It's the modern alternative to the old #ifndef / #define / #endif include guard pattern.

#include <string>
#include <sstream>
#include <chrono>
#include <cstdint>   // for uint64_t

// INTERVIEW NOTE: We use 'enum class' (scoped enum) rather than plain 'enum'.
// With a plain enum, BUY and SELL leak into the global namespace and can clash.
// With enum class, you must write OrderSide::BUY — no name collisions possible.
enum class OrderSide {
    BUY,
    SELL
};

enum class OrderType {
    LIMIT,   // Fill only at the specified price or better
    MARKET   // Fill immediately at the best available price (we'll use this in later days)
};

struct Order {
    // INTERVIEW NOTE: uint64_t (unsigned 64-bit integer) holds values 0 to ~18 quintillion.
    // A plain 'int' is only 32-bit and could overflow on a busy exchange that processes
    // billions of orders. Using uint64_t also communicates intent: IDs are never negative.
    uint64_t id;

    OrderSide side;     // BUY or SELL
    OrderType type;     // LIMIT or MARKET

    // INTERVIEW NOTE: 'double' for price is fine for a simulator, but real exchanges
    // use fixed-point integers (e.g., price in hundredths of a cent) to avoid
    // floating-point rounding errors in financial calculations.
    double price;

    uint64_t quantity;  // Number of shares/contracts

    // INTERVIEW NOTE: std::chrono::system_clock::time_point is type-safe and portable.
    // A plain 'int' unix timestamp would:
    //   1. Overflow in 2038 on 32-bit systems (the Y2K38 problem)
    //   2. Require manual conversion to make it human-readable
    //   3. Give no compile-time indication of what units it represents
    // std::chrono forces you to be explicit about durations and time units.
    std::chrono::system_clock::time_point timestamp;

    bool is_filled = false;  // Default member initialiser — requires C++11 or later

    // 'const' after the method name means this method does NOT modify the struct.
    // This is called a "const member function". Good habit: mark anything read-only as const.
    std::string toString() const {
        std::ostringstream oss;  // String stream: build a string piece by piece, like Python's f-string

        oss << "Order["
            << "id=" << id
            << " side=" << (side == OrderSide::BUY ? "BUY" : "SELL")
            << " type=" << (type == OrderType::LIMIT ? "LIMIT" : "MARKET")
            << " price=" << price
            << " qty=" << quantity
            << " filled=" << (is_filled ? "yes" : "no");

        // Convert chrono time_point to a unix timestamp (seconds since epoch) for printing
        auto epoch_seconds = std::chrono::duration_cast<std::chrono::seconds>(
            timestamp.time_since_epoch()
        ).count();
        oss << " ts=" << epoch_seconds << "]";

        return oss.str();
    }
};
