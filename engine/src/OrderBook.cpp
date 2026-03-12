#include "OrderBook.h"
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <limits>

void OrderBook::addOrder(Order order) {
    // MARKET orders get sentinel prices so they always cross the spread.
    if (order.type == OrderType::MARKET) {
        order.price = (order.side == OrderSide::BUY)
                      ? std::numeric_limits<double>::max()
                      : 0.0;
    }

    if (order.side == OrderSide::BUY)
        bids[order.price].push_back(order);
    else
        asks[order.price].push_back(order);

    order_index[order.id] = {order.side, order.price};

    if (order.type == OrderType::MARKET) {
        match();
        // Discard any unfilled remainder at the sentinel price level.
        // INTERVIEW NOTE: A market order has no price constraint, so it cannot
        // rest — whatever doesn't fill is cancelled. This is "walking the book":
        // each fill occurs at a worse price than the last (slippage).
        if (order.side == OrderSide::BUY) {
            auto it = bids.find(std::numeric_limits<double>::max());
            if (it != bids.end()) {
                for (const auto& o : it->second) order_index.erase(o.id);
                bids.erase(it);
            }
        } else {
            auto it = asks.find(0.0);
            if (it != asks.end()) {
                for (const auto& o : it->second) order_index.erase(o.id);
                asks.erase(it);
            }
        }
    }
}

double OrderBook::getBestBid() const {
    return bids.empty() ? 0.0 : bids.begin()->first;
}

double OrderBook::getBestAsk() const {
    return asks.empty() ? 0.0 : asks.begin()->first;
}

void OrderBook::printBook() const {
    std::cout << "\n========== ORDER BOOK ==========\n";
    std::cout << std::fixed << std::setprecision(2);

    std::cout << "  ASKS (lowest = best):\n";
    int n = 0;
    for (const auto& [price, deq] : asks) {
        uint64_t qty = 0;
        for (const auto& o : deq) qty += o.quantity;
        std::cout << "    ASK  " << price << "  qty=" << qty << "\n";
        if (++n >= 5) break;
    }

    std::cout << "  --------------------------------\n  SPREAD = ";
    if (!bids.empty() && !asks.empty())
        std::cout << (getBestAsk() - getBestBid()) << "\n";
    else
        std::cout << "N/A\n";
    std::cout << "  --------------------------------\n";

    std::cout << "  BIDS (highest = best):\n";
    n = 0;
    for (const auto& [price, deq] : bids) {
        uint64_t qty = 0;
        for (const auto& o : deq) qty += o.quantity;
        std::cout << "    BID  " << price << "  qty=" << qty << "\n";
        if (++n >= 5) break;
    }
    std::cout << "=================================\n\n";
}

void OrderBook::match() {
    while (!bids.empty() && !asks.empty() &&
           bids.begin()->first >= asks.begin()->first)
    {
        Order& bid_order = bids.begin()->second.front();
        Order& ask_order = asks.begin()->second.front();

        uint64_t fill_qty = std::min(bid_order.quantity, ask_order.quantity);

        // Trade price = ask price: the passive (resting) side sets the price.
        Trade t;
        t.trade_id      = next_trade_id++;
        t.buy_order_id  = bid_order.id;
        t.sell_order_id = ask_order.id;
        t.price         = asks.begin()->first;
        t.quantity      = fill_qty;
        t.timestamp     = std::chrono::system_clock::now();
        trade_log.push_back(t);

        bid_order.quantity -= fill_qty;
        ask_order.quantity -= fill_qty;

        // Save IDs before pop_front() invalidates references.
        if (ask_order.quantity == 0) {
            uint64_t id = ask_order.id;
            asks.begin()->second.pop_front();
            order_index.erase(id);
            if (asks.begin()->second.empty()) asks.erase(asks.begin());
        }
        if (bid_order.quantity == 0) {
            uint64_t id = bid_order.id;
            bids.begin()->second.pop_front();
            order_index.erase(id);
            if (bids.begin()->second.empty()) bids.erase(bids.begin());
        }
    }
}

bool OrderBook::cancelOrder(uint64_t order_id) {
    auto idx_it = order_index.find(order_id);
    if (idx_it == order_index.end())
        return false;  // already filled, cancelled, or never existed

    auto [side, price] = idx_it->second;

    auto cancel_in = [&](auto& book_side) -> bool {
        auto map_it = book_side.find(price);
        if (map_it == book_side.end()) return false;
        auto& deq = map_it->second;
        for (auto it = deq.begin(); it != deq.end(); ++it) {
            if (it->id == order_id) {
                deq.erase(it);
                if (deq.empty()) book_side.erase(map_it);
                order_index.erase(idx_it);
                return true;
            }
        }
        return false;
    };

    if (side == OrderSide::BUY) return cancel_in(bids);
    else                        return cancel_in(asks);
}

BookSnapshot OrderBook::getSnapshot() const {
    BookSnapshot snap;

    int count = 0;
    for (const auto& [price, deq] : bids) {
        if (count++ >= 5) break;
        PriceLevel lvl{price, 0, static_cast<int>(deq.size())};
        for (const auto& o : deq) lvl.total_quantity += o.quantity;
        snap.bids.push_back(lvl);
    }

    count = 0;
    for (const auto& [price, deq] : asks) {
        if (count++ >= 5) break;
        PriceLevel lvl{price, 0, static_cast<int>(deq.size())};
        for (const auto& o : deq) lvl.total_quantity += o.quantity;
        snap.asks.push_back(lvl);
    }

    if (!bids.empty() && !asks.empty()) {
        snap.spread    = asks.begin()->first - bids.begin()->first;
        snap.mid_price = (bids.begin()->first + asks.begin()->first) / 2.0;
    } else {
        snap.spread = snap.mid_price = 0.0;
    }

    snap.timestamp = std::chrono::system_clock::now();
    return snap;
}

void OrderBook::printTradeLog() const {
    std::cout << "\n========== TRADE LOG ==========\n";
    if (trade_log.empty())
        std::cout << "  (no trades executed)\n";
    else
        for (const Trade& t : trade_log) std::cout << "  " << t.toString() << "\n";
    std::cout << "================================\n\n";
}
