#include <iostream>
#include <iomanip>
#include <random>
#include <chrono>
#include "Order.h"
#include "OrderBook.h"

int main() {
    constexpr int NUM_ORDERS = 1'000'000;

    // Fixed seed → reproducible order sequence every run.
    std::mt19937 rng(42);
    std::uniform_real_distribution<double> price_dist(188.00, 190.00);
    std::uniform_int_distribution<uint64_t> qty_dist(10, 200);

    OrderBook book;

    // Pre-generate orders before starting the timer so RNG overhead is excluded.
    std::vector<Order> orders;
    orders.reserve(NUM_ORDERS);

    auto now_tp = std::chrono::system_clock::now();
    for (int i = 0; i < NUM_ORDERS; ++i) {
        orders.push_back({
            static_cast<uint64_t>(i + 1),
            (i % 2 == 0) ? OrderSide::BUY : OrderSide::SELL,
            OrderType::LIMIT,
            price_dist(rng),
            qty_dist(rng),
            now_tp,
            false
        });
    }

    // INTERVIEW NOTE: high_resolution_clock is monotonic — it never jumps backward
    // (unlike system_clock which can be adjusted by NTP). Always use it for elapsed time.
    auto t_start = std::chrono::high_resolution_clock::now();

    for (const auto& o : orders) {
        book.addOrder(o);
        book.match();
    }

    auto t_end = std::chrono::high_resolution_clock::now();

    double elapsed_ms    = std::chrono::duration<double, std::milli>(t_end - t_start).count();
    double orders_per_sec = NUM_ORDERS / (elapsed_ms / 1000.0);

    BookSnapshot snap = book.getSnapshot();

    std::cout << std::fixed << std::setprecision(2)
              << "\n========== BENCHMARK RESULTS ==========\n"
              << "  Total orders processed : " << NUM_ORDERS << "\n"
              << "  Total time             : " << elapsed_ms << " ms\n"
              << "  Orders per second      : " << static_cast<long long>(orders_per_sec) << "\n"
              << "  Total trades executed  : " << book.tradeCount() << "\n"
              << "  Bid levels remaining   : " << snap.bids.size() << " (top 5)\n"
              << "  Ask levels remaining   : " << snap.asks.size() << " (top 5)\n"
              << "=======================================\n\n";

    // INTERVIEW NOTE: To push this number higher — replace std::map with a flat array
    // indexed by price tick (O(1) vs O(log n)), use memory pools to cut allocation
    // overhead, and pin the matching thread to one CPU core to reduce cache misses.

    return 0;
}
