#include <pybind11/pybind11.h>
#include <pybind11/stl.h>      // automatic std::vector <-> Python list conversion
#include <pybind11/chrono.h>   // automatic std::chrono <-> Python datetime conversion

#include "Order.h"
#include "Trade.h"
#include "OrderBook.h"

namespace py = pybind11;

PYBIND11_MODULE(engine, m) {
    m.doc() = "C++ matching engine — Python bindings (Day 10-11)";

    // ── OrderSide enum ────────────────────────────────────────────────────
    // py::enum_ wraps a C++ enum class so Python sees engine.OrderSide.BUY.
    // export_values() also injects BUY/SELL into the module namespace (optional).
    py::enum_<OrderSide>(m, "OrderSide")
        .value("BUY",  OrderSide::BUY)
        .value("SELL", OrderSide::SELL)
        .export_values();

    // ── OrderType enum ────────────────────────────────────────────────────
    py::enum_<OrderType>(m, "OrderType")
        .value("LIMIT",  OrderType::LIMIT)
        .value("MARKET", OrderType::MARKET)
        .export_values();

    // ── Order struct ──────────────────────────────────────────────────────
    // The test passes timestamp as int nanoseconds: int(time.time() * 1e9)
    // We use a lambda constructor to convert that int → chrono::time_point..
    py::class_<Order>(m, "Order")
        .def(py::init([](uint64_t id,
                         OrderSide side,
                         OrderType type,
                         double price,
                         uint64_t quantity,
                         long long ts_ns,
                         bool is_filled) {
                Order o;
                o.id        = id;
                o.side      = side;
                o.type      = type;
                o.price     = price;
                o.quantity  = quantity;
                // Convert nanoseconds-since-epoch integer → chrono time_point
                o.timestamp = std::chrono::system_clock::time_point(
                                std::chrono::duration_cast<std::chrono::system_clock::duration>(
                                    std::chrono::nanoseconds(ts_ns)));
                o.is_filled = is_filled;
                return o;
             }),
             py::arg("id"),
             py::arg("side"),
             py::arg("type"),
             py::arg("price"),
             py::arg("quantity"),
             py::arg("timestamp_ns"),
             py::arg("is_filled") = false)
        .def_readonly("id",        &Order::id)
        .def_readonly("side",      &Order::side)
        .def_readonly("type",      &Order::type)
        .def_readonly("price",     &Order::price)
        .def_readonly("quantity",  &Order::quantity)
        .def_readonly("is_filled", &Order::is_filled)
        .def("__repr__",           &Order::toString);

    // ── Trade struct ──────────────────────────────────────────────────────
    py::class_<Trade>(m, "Trade")
        .def_readonly("trade_id",      &Trade::trade_id)
        .def_readonly("buy_order_id",  &Trade::buy_order_id)
        .def_readonly("sell_order_id", &Trade::sell_order_id)
        .def_readonly("price",         &Trade::price)
        .def_readonly("quantity",      &Trade::quantity)
        .def("__repr__",               &Trade::toString);

    // ── PriceLevel struct ─────────────────────────────────────────────────
    py::class_<PriceLevel>(m, "PriceLevel")
        .def_readonly("price",          &PriceLevel::price)
        .def_readonly("total_quantity", &PriceLevel::total_quantity)
        .def_readonly("order_count",    &PriceLevel::order_count);

    // ── BookSnapshot struct ───────────────────────────────────────────────
    // pybind11/stl.h makes bids/asks (std::vector<PriceLevel>) automatically
    // become Python lists of PriceLevel objects — no extra work needed.
    py::class_<BookSnapshot>(m, "BookSnapshot")
        .def_readonly("bids",      &BookSnapshot::bids)
        .def_readonly("asks",      &BookSnapshot::asks)
        .def_readonly("spread",    &BookSnapshot::spread)
        .def_readonly("mid_price", &BookSnapshot::mid_price);

    // ── OrderBook class ───────────────────────────────────────────────────
    // py::class_ wraps the C++ class. def(py::init<>()) exposes the default
    // constructor so Python can do: ob = engine.OrderBook()
    py::class_<OrderBook>(m, "OrderBook")
        .def(py::init<>())
        .def("addOrder",      &OrderBook::addOrder,    "Add an order to the book.")
        .def("match",         &OrderBook::match,       "Run the price-time-priority matching loop.")
        .def("cancelOrder",   &OrderBook::cancelOrder, "Cancel order by ID. Returns True if found.")
        .def("getSnapshot",   &OrderBook::getSnapshot, "Return a BookSnapshot of the top 5 levels.")
        .def("getBestBid",    &OrderBook::getBestBid,  "Return the highest bid price (0.0 if empty).")
        .def("getBestAsk",    &OrderBook::getBestAsk,  "Return the lowest ask price (0.0 if empty).")
        .def("printBook",     &OrderBook::printBook,   "Print the order book to stdout.")
        .def("printTradeLog", &OrderBook::printTradeLog, "Print all executed trades to stdout.")
        .def("tradeCount",    &OrderBook::tradeCount,  "Return the number of trades executed.");
}
