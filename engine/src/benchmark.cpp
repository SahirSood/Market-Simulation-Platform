#include <iostream>
#include <iomanip>
#include <random>
#include <chrono>
#include "Order.h"
#include "OrderBook.h"

// ═══════════════════════════════════════════════════════════════════════
// DAY 9 — Throughput Benchmark
//
// INTERVIEW NOTE: "Throughput" = how many operations the system can
// process per unit of time. For a matching engine the key metric is
// orders/second. HFT shops measure in microseconds per order and
// optimise down to the nanosecond. Our engine is a correct, readable
// simulator — not a production low-latency system — so the number here
// sets a baseline to reason about.
// ═══════════════════════════════════════════════════════════════════════

int main() {
    constexpr int NUM_ORDERS = 1'000'000;

    // ── Random number generator ─────────────────────────────────────────
    std::mt19937 rng(42);

    // Prices clustered around 189.00 ± 1.00, simulating a realistic spread.
    // Alternating BUY/SELL at overlapping prices means many orders will match.
    std::uniform_real_distribution<double> price_dist(188.00, 190.00);
    std::uniform_int_distribution<uint64_t> qty_dist(10, 200);

    OrderBook book;

    // Pre-generate all orders before starting the timer so we measure
    // matching throughput only, not random number generation overhead.
    std::vector<Order> orders;
    orders.reserve(NUM_ORDERS);

    auto now_tp = std::chrono::system_clock::now();
    for (int i = 0; i < NUM_ORDERS; ++i) {
        Order o;
        o.id        = static_cast<uint64_t>(i + 1);
        o.side      = (i % 2 == 0) ? OrderSide::BUY : OrderSide::SELL;
        o.type      = OrderType::LIMIT;
        o.price     = price_dist(rng);
        o.quantity  = qty_dist(rng);
        o.timestamp = now_tp;
        o.is_filled = false;
        orders.push_back(o);
    }

    // ── Start timer ──────────────────────────────────────────────────────
    auto t_start = std::chrono::high_resolution_clock::now();

    // ── Submit all orders ────────────────────────────────────────────────
    for (const auto& o : orders) {
        book.addOrder(o);
        book.match();
    }

    // ── Stop timer ───────────────────────────────────────────────────────
    auto t_end = std::chrono::high_resolution_clock::now();

    // ── Results ──────────────────────────────────────────────────────────
    double elapsed_ms = std::chrono::duration<double, std::milli>(t_end - t_start).count();
    double elapsed_s  = elapsed_ms / 1000.0;
    double orders_per_sec = NUM_ORDERS / elapsed_s;

    // Book depth after all orders settle.
    int bid_levels = 0, ask_levels = 0;
    {
        BookSnapshot snap = book.getSnapshot();
        // getSnapshot() only shows top 5 — for depth we need the raw count.
        // We use a workaround: count levels via repeated snapshot calls isn't
        // ideal; in production you'd expose a depth() method. For now we note
        // this limitation with a comment and report the top-5 visible levels.
        bid_levels = static_cast<int>(snap.bids.size());
        ask_levels = static_cast<int>(snap.asks.size());
    }

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "\n========== BENCHMARK RESULTS ==========\n";
    std::cout << "  Total orders processed : " << NUM_ORDERS        << "\n";
    std::cout << "  Total time             : " << elapsed_ms        << " ms\n";
    std::cout << "  Orders per second      : " << static_cast<long long>(orders_per_sec) << "\n";
    std::cout << "  Total trades executed  : " << book.tradeCount() << "\n";
    std::cout << "  Bid levels remaining   : " << bid_levels << " (top 5 shown)\n";
    std::cout << "  Ask levels remaining   : " << ask_levels << " (top 5 shown)\n";
    std::cout << "=======================================\n\n";

    // INTERVIEW NOTE: What affects this number?
    //
    //  FASTER:
    //    - Use arrays instead of std::map (flat order book with fixed price
    //      granularity, like LMAX Exchange's "ring buffer" design)
    //    - Avoid heap allocation in the hot path (object pools, arena allocators)
    //    - Lock-free data structures for multi-threaded matching
    //    - Compiler optimisations: -O3, profile-guided optimisation (PGO)
    //    - CPU affinity: pin the matching thread to one core to avoid cache misses
    //
    //  SLOWER:
    //    - More unique price levels → deeper map → more O(log n) traversals
    //    - Wider price range in this benchmark → fewer matches → more levels build up
    //    - Printing / I/O inside the hot loop (we avoid this here)
    //    - Memory allocation churn (push_back on deques allocates)
    //
    //  WHY HFT SHOPS CARE:
    //    On NASDAQ the matching engine processes ~500K–2M messages/second.
    //    At 1 microsecond/order, a 1ns improvement across 1M orders/sec
    //    = 1ms/sec saved = potential edge in latency-sensitive strategies.

    return 0;
}
