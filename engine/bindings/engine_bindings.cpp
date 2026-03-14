#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/chrono.h>

#include "Order.h"
#include "Trade.h"
#include "OrderBook.h"

namespace py = pybind11;

PYBIND11_MODULE(engine, m) {
    m.doc() = "C++ matching engine — Python bindings";

    py::enum_<OrderSide>(m, "OrderSide")
        .value("BUY",  OrderSide::BUY)
        .value("SELL", OrderSide::SELL)
        .export_values();

    py::enum_<OrderType>(m, "OrderType")
        .value("LIMIT",  OrderType::LIMIT)
        .value("MARKET", OrderType::MARKET)
        .export_values();

    // Lambda constructor converts Python int (nanoseconds) to chrono::time_point.
    py::class_<Order>(m, "Order")
        .def(py::init([](uint64_t id, OrderSide side, OrderType type,
                         double price, uint64_t quantity,
                         long long ts_ns, bool is_filled) {
                Order o;
                o.id        = id;
                o.side      = side;
                o.type      = type;
                o.price     = price;
                o.quantity  = quantity;
                o.timestamp = std::chrono::system_clock::time_point(
                    std::chrono::duration_cast<std::chrono::system_clock::duration>(
                        std::chrono::nanoseconds(ts_ns)));
                o.is_filled = is_filled;
                return o;
             }),
             py::arg("id"), py::arg("side"), py::arg("type"),
             py::arg("price"), py::arg("quantity"),
             py::arg("timestamp_ns"), py::arg("is_filled") = false)
        .def_readonly("id",        &Order::id)
        .def_readonly("side",      &Order::side)
        .def_readonly("type",      &Order::type)
        .def_readonly("price",     &Order::price)
        .def_readonly("quantity",  &Order::quantity)
        .def_readonly("is_filled", &Order::is_filled)
        .def("__repr__",           &Order::toString);

    py::class_<Trade>(m, "Trade")
        .def_readonly("trade_id",      &Trade::trade_id)
        .def_readonly("buy_order_id",  &Trade::buy_order_id)
        .def_readonly("sell_order_id", &Trade::sell_order_id)
        .def_readonly("price",         &Trade::price)
        .def_readonly("quantity",      &Trade::quantity)
        .def("__repr__",               &Trade::toString);

    py::class_<PriceLevel>(m, "PriceLevel")
        .def_readonly("price",          &PriceLevel::price)
        .def_readonly("total_quantity", &PriceLevel::total_quantity)
        .def_readonly("order_count",    &PriceLevel::order_count);

    py::class_<BookSnapshot>(m, "BookSnapshot")
        .def_readonly("bids",      &BookSnapshot::bids)
        .def_readonly("asks",      &BookSnapshot::asks)
        .def_readonly("spread",    &BookSnapshot::spread)
        .def_readonly("mid_price", &BookSnapshot::mid_price);

    py::class_<OrderBook>(m, "OrderBook")
        .def(py::init<>())
        .def("addOrder",      &OrderBook::addOrder)
        .def("match",         &OrderBook::match)
        .def("cancelOrder",   &OrderBook::cancelOrder)
        .def("getSnapshot",   &OrderBook::getSnapshot)
        .def("getBestBid",    &OrderBook::getBestBid)
        .def("getBestAsk",    &OrderBook::getBestAsk)
        .def("printBook",     &OrderBook::printBook)
        .def("printTradeLog", &OrderBook::printTradeLog)
        .def("tradeCount",    &OrderBook::tradeCount)
        .def("getTrades",     &OrderBook::getTrades,
             py::arg("since_index") = 0,
             "Return trades from since_index onward. "
             "Pass tradeCount() before addOrder() to get only new trades.");
}
