#include <gtest/gtest.h>
#include "OrderBook.h"

// Helper: build an Order without repeating the timestamp boilerplate every time.
// INTERVIEW NOTE: keeping test helpers small and focused makes each TEST() read
// like a specification — intent is clear at a glance.
static Order makeOrder(uint64_t id, OrderSide side, OrderType type,
                       double price, uint64_t qty) {
    return Order{id, side, type, price, qty,
                 std::chrono::system_clock::now(), false};
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 1 — Limit order fully matches
// BUY 100 @ 190, SELL 100 @ 190 → 1 trade of 100 @ 190, book empty
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, LimitOrderMatch) {
    OrderBook book;
    book.addOrder(makeOrder(1, OrderSide::BUY,  OrderType::LIMIT, 190.0, 100));
    book.addOrder(makeOrder(2, OrderSide::SELL, OrderType::LIMIT, 190.0, 100));
    book.match();

    EXPECT_EQ(book.tradeCount(), 1u);
    // Both sides fully consumed — book should be empty.
    EXPECT_EQ(book.getBestBid(),  0.0);
    EXPECT_EQ(book.getBestAsk(),  0.0);
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 2 — Partial fill
// BUY 100 @ 190, SELL 60 @ 190 → trade of 60, 40 remain on bid side
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, PartialFill) {
    OrderBook book;
    book.addOrder(makeOrder(1, OrderSide::BUY,  OrderType::LIMIT, 190.0, 100));
    book.addOrder(makeOrder(2, OrderSide::SELL, OrderType::LIMIT, 190.0,  60));
    book.match();

    EXPECT_EQ(book.tradeCount(), 1u);
    // 40 shares still resting on the bid.
    // INTERVIEW NOTE: getBestBid() returning 190.0 confirms the price level
    // was NOT erased — only the fully-filled ask was removed.
    EXPECT_EQ(book.getBestBid(), 190.0);
    EXPECT_EQ(book.getBestAsk(),   0.0);  // ask side empty
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 3 — Market order fully fills (enough liquidity)
// Asks: 30@189.10, 30@189.20, 20@189.30 (total=80)
// MARKET BUY 80 → 3 trades, asks wiped out
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, MarketOrderFullFill) {
    OrderBook book;
    book.addOrder(makeOrder(1, OrderSide::SELL, OrderType::LIMIT, 189.10, 30));
    book.addOrder(makeOrder(2, OrderSide::SELL, OrderType::LIMIT, 189.20, 30));
    book.addOrder(makeOrder(3, OrderSide::SELL, OrderType::LIMIT, 189.30, 20));

    // addOrder() for a MARKET order internally calls match() and cleans up.
    book.addOrder(makeOrder(4, OrderSide::BUY, OrderType::MARKET, 0.0, 80));

    // INTERVIEW NOTE: 3 separate price levels → 3 separate trade records.
    EXPECT_EQ(book.tradeCount(), 3u);
    EXPECT_EQ(book.getBestAsk(), 0.0);  // all asks consumed
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 4 — Market order partial fill (insufficient liquidity)
// Asks: 50@189.10, 30@189.20, 40@189.30 (total=120)
// MARKET BUY 200 → 3 trades, 80 remainder cancelled, both sides empty
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, MarketOrderPartial) {
    OrderBook book;
    book.addOrder(makeOrder(1, OrderSide::SELL, OrderType::LIMIT, 189.10, 50));
    book.addOrder(makeOrder(2, OrderSide::SELL, OrderType::LIMIT, 189.20, 30));
    book.addOrder(makeOrder(3, OrderSide::SELL, OrderType::LIMIT, 189.30, 40));

    book.addOrder(makeOrder(4, OrderSide::BUY, OrderType::MARKET, 0.0, 200));

    EXPECT_EQ(book.tradeCount(), 3u);
    // Market remainder (80 shares at DBL_MAX) must have been cancelled.
    EXPECT_EQ(book.getBestBid(), 0.0);
    EXPECT_EQ(book.getBestAsk(), 0.0);
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 5 — Cancel then no match
// Add BUY@190, cancel it, add matching SELL@190 → no trade
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, CancelThenNoMatch) {
    OrderBook book;
    book.addOrder(makeOrder(1, OrderSide::BUY, OrderType::LIMIT, 190.0, 100));

    bool result = book.cancelOrder(1);
    EXPECT_TRUE(result);  // cancel succeeded

    book.addOrder(makeOrder(2, OrderSide::SELL, OrderType::LIMIT, 190.0, 100));
    book.match();

    // The cancelled BUY is gone; the SELL has nothing to match against.
    // INTERVIEW NOTE: verifying tradeCount()==0 is the key assertion —
    // it proves the cancelled order is truly absent from the book.
    EXPECT_EQ(book.tradeCount(), 0u);
    EXPECT_EQ(book.getBestAsk(), 190.0);  // SELL still resting
    EXPECT_EQ(book.getBestBid(),   0.0);  // bid side empty
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 6 — Cancel non-existent order returns false
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, CancelNonExistent) {
    OrderBook book;
    // INTERVIEW NOTE: on a real exchange this is the graceful path for a
    // cancel arriving after the order already filled (cancel-vs-fill race).
    EXPECT_FALSE(book.cancelOrder(999));
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 7 — Empty book returns 0.0 for best bid and ask
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, EmptyBook) {
    OrderBook book;
    EXPECT_EQ(book.getBestBid(), 0.0);
    EXPECT_EQ(book.getBestAsk(), 0.0);
}

// ─────────────────────────────────────────────────────────────────────────────
// TEST 8 — Trade log accumulates correctly
// 3 separate crossing pairs → exactly 3 trades
// ─────────────────────────────────────────────────────────────────────────────
TEST(OrderBookTest, TradeLogCount) {
    OrderBook book;

    // Pair 1
    book.addOrder(makeOrder(1, OrderSide::BUY,  OrderType::LIMIT, 190.0, 10));
    book.addOrder(makeOrder(2, OrderSide::SELL, OrderType::LIMIT, 190.0, 10));
    book.match();

    // Pair 2
    book.addOrder(makeOrder(3, OrderSide::BUY,  OrderType::LIMIT, 191.0, 20));
    book.addOrder(makeOrder(4, OrderSide::SELL, OrderType::LIMIT, 191.0, 20));
    book.match();

    // Pair 3
    book.addOrder(makeOrder(5, OrderSide::BUY,  OrderType::LIMIT, 192.0, 30));
    book.addOrder(makeOrder(6, OrderSide::SELL, OrderType::LIMIT, 192.0, 30));
    book.match();

    // INTERVIEW NOTE: trade_log is append-only; tradeCount() lets tests inspect
    // it without exposing the internal vector.
    EXPECT_EQ(book.tradeCount(), 3u);
}
