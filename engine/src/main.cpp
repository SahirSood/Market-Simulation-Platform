#include <iostream>
#include "Order.h"   // Our new header — the compiler finds this because CMakeLists.txt
                     // has 'target_include_directories(... PRIVATE include)'

int main() {
    std::cout << "=== Day 2: Order and Trade Structs ===\n\n";

    // std::chrono::system_clock::now() captures the current wall-clock time.
    // We'll use the same timestamp for all orders in this demo — in real code
    // each order would get its own timestamp at the moment it arrives.
    auto now = std::chrono::system_clock::now();

    // INTERVIEW NOTE: In C++, struct members are public by default.
    // We're using "aggregate initialisation" here — listing values in the order
    // the fields are declared in the struct. No constructor needed for a plain struct.
    // This style (struct instead of class + explicit setters) is common in
    // performance-critical systems because it avoids function call overhead.

    // --- 5 BUY limit orders ---
    Order buy1  = {1, OrderSide::BUY,  OrderType::LIMIT, 189.00, 100, now, false};
    Order buy2  = {2, OrderSide::BUY,  OrderType::LIMIT, 189.10,  50, now, false};
    Order buy3  = {3, OrderSide::BUY,  OrderType::LIMIT, 188.90,  75, now, false};
    Order buy4  = {4, OrderSide::BUY,  OrderType::LIMIT, 189.05,  30, now, false};
    Order buy5  = {5, OrderSide::BUY,  OrderType::LIMIT, 188.95, 200, now, false};

    // --- 5 SELL limit orders ---
    Order sell1 = {6,  OrderSide::SELL, OrderType::LIMIT, 189.20, 100, now, false};
    Order sell2 = {7,  OrderSide::SELL, OrderType::LIMIT, 189.15,  80, now, false};
    Order sell3 = {8,  OrderSide::SELL, OrderType::LIMIT, 189.30,  60, now, false};
    Order sell4 = {9,  OrderSide::SELL, OrderType::LIMIT, 189.25,  40, now, false};
    Order sell5 = {10, OrderSide::SELL, OrderType::LIMIT, 189.10, 150, now, false};

    std::cout << "--- BUY ORDERS ---\n";
    std::cout << buy1.toString()  << "\n";
    std::cout << buy2.toString()  << "\n";
    std::cout << buy3.toString()  << "\n";
    std::cout << buy4.toString()  << "\n";
    std::cout << buy5.toString()  << "\n";

    std::cout << "\n--- SELL ORDERS ---\n";
    std::cout << sell1.toString() << "\n";
    std::cout << sell2.toString() << "\n";
    std::cout << sell3.toString() << "\n";
    std::cout << sell4.toString() << "\n";
    std::cout << sell5.toString() << "\n";

    return 0;
}
