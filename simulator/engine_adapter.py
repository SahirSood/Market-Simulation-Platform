"""
EngineAdapter — single thread-safe gateway to the C++ matching engine.

All Python code that submits orders or cancels must go through here.
One engine.OrderBook is maintained per ticker.

Fill detection note
-------------------
The current pybind11 binding exposes tradeCount() and printTradeLog() (stdout).
getTrades() is added in Day 8 (engine/bindings/engine_bindings.cpp). Until that
build is available, _extract_fills() approximates fills from the tradeCount delta.
Once getTrades() is live, swap _extract_fills() to use it instead.
"""
import sys
import time
import threading
import logging
from collections import defaultdict
from pathlib import Path

from portfolio import FillRecord

# Ensure the compiled engine module is on the path regardless of build type.
_ENGINE_BUILD_DIR = Path(__file__).parent.parent / "engine" / "build"
for _ENGINE_DIR in (
    _ENGINE_BUILD_DIR / "Debug",
    _ENGINE_BUILD_DIR / "Release",
    _ENGINE_BUILD_DIR,
):
    if _ENGINE_DIR.exists() and str(_ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(_ENGINE_DIR))

logger = logging.getLogger(__name__)

# How many consecutive submit errors before a ticker is suspended
_CIRCUIT_BREAKER_THRESHOLD = 3
_CIRCUIT_BREAKER_COOLDOWN  = 60.0   # seconds
_REQUIRED_ENGINE_API = ("OrderBook", "Order", "OrderSide", "OrderType")


def is_native_engine_module(module) -> bool:
    """Return True when an imported module exposes the pybind engine contract."""
    return all(hasattr(module, name) for name in _REQUIRED_ENGINE_API)


class EngineAdapter:
    """
    Thread-safe wrapper around the C++ engine.OrderBook.
    One OrderBook per ticker; a single lock guards all operations.
    """

    def __init__(self):
        # Lazily import the compiled engine module so tests can mock it
        try:
            import engine as _engine_module
            if is_native_engine_module(_engine_module):
                self._engine = _engine_module
            else:
                logger.warning(
                    "Imported engine module is missing the pybind API — "
                    "EngineAdapter running in stub mode. Build the native "
                    "extension before running live matching."
                )
                self._engine = None
        except ImportError:
            logger.warning(
                "C++ engine module not found — EngineAdapter running in stub mode. "
                "Build the pybind11 extension before running the full system."
            )
            self._engine = None

        self._books:   dict[str, object] = {}   # ticker → engine.OrderBook
        self._lock:    threading.Lock    = threading.Lock()
        self._next_id: int               = 1

        # Maps order_id → (ticker, side) for bookkeeping
        self._pending: dict[int, tuple[str, str]] = {}

        # Circuit breaker: consecutive error counts per ticker
        self._error_counts:    dict[str, int]   = defaultdict(int)
        self._suspended_until: dict[str, float] = {}

    # ── Public interface ───────────────────────────────────────────────────────

    def submit(
        self,
        ticker:     str,
        side:       str,        # "BUY" | "SELL"
        order_type: str,        # "LIMIT" | "MARKET"
        price:      float,
        quantity:   int,
        bot_id:     str = "unknown",
    ) -> tuple[int, list[FillRecord]]:
        """
        Submit an order to the book for the given ticker.
        Returns (order_id, list_of_fills).
        Raises RuntimeError if the ticker is circuit-breaker suspended.
        """
        with self._lock:
            # Circuit breaker check
            suspended_until = self._suspended_until.get(ticker, 0.0)
            if time.time() < suspended_until:
                remaining = int(suspended_until - time.time())
                raise RuntimeError(
                    f"[EngineAdapter] {ticker} is circuit-breaker suspended "
                    f"for {remaining}s more"
                )

            if self._engine is None:
                # Stub mode: assign an ID but no real matching
                order_id = self._next_id
                self._next_id += 1
                logger.debug(f"[EngineAdapter/stub] {side} {quantity} {ticker} @ {price}")
                return order_id, []

            try:
                book = self._get_or_create_book(ticker)

                order_id = self._next_id
                self._next_id += 1

                e_side = (self._engine.OrderSide.BUY
                          if side == "BUY" else self._engine.OrderSide.SELL)
                e_type = (self._engine.OrderType.LIMIT
                          if order_type == "LIMIT" else self._engine.OrderType.MARKET)

                trades_before = book.tradeCount()

                order = self._engine.Order(
                    id=order_id,
                    side=e_side,
                    type=e_type,
                    price=price,
                    quantity=quantity,
                    timestamp_ns=int(time.time_ns()),
                )
                book.addOrder(order)

                trades_after = book.tradeCount()
                fills = self._extract_fills(
                    ticker, side, order_id, quantity, price,
                    trades_before, trades_after,
                    book,
                )

                self._pending[order_id] = (ticker, side)
                # Reset circuit breaker on success
                self._error_counts[ticker] = 0
                return order_id, fills

            except Exception as e:
                self._error_counts[ticker] += 1
                count = self._error_counts[ticker]
                logger.error(
                    f"[EngineAdapter] submit failed for {ticker} "
                    f"(error #{count}): {e}"
                )
                if count >= _CIRCUIT_BREAKER_THRESHOLD:
                    self._suspended_until[ticker] = time.time() + _CIRCUIT_BREAKER_COOLDOWN
                    logger.critical(
                        f"[EngineAdapter] Circuit breaker OPEN for {ticker} "
                        f"— suspended {_CIRCUIT_BREAKER_COOLDOWN}s"
                    )
                raise

    def cancel(self, order_id: int) -> bool:
        """Cancel a resting order by id. Returns True if cancelled, False if not found."""
        with self._lock:
            info = self._pending.get(order_id)
            if not info:
                return False
            ticker, _ = info
            book = self._books.get(ticker)
            if not book:
                return False
            try:
                result = book.cancelOrder(order_id)
                if result:
                    del self._pending[order_id]
                return result
            except Exception as e:
                logger.error(f"[EngineAdapter] cancel({order_id}) failed: {e}")
                return False

    def get_snapshot(self, ticker: str):
        """Return the current BookSnapshot for a ticker."""
        with self._lock:
            if self._engine is None:
                return None
            book = self._get_or_create_book(ticker)
            return book.getSnapshot()

    def get_trade_count(self, ticker: str) -> int:
        """Return total trades executed in the book for this ticker."""
        with self._lock:
            book = self._books.get(ticker)
            if book is None:
                return 0
            return book.tradeCount()

    def seed_liquidity(
        self,
        ticker: str,
        mid_price: float,
        levels: int = 3,
        quantity: int = 500,
        spread_pct: float = 0.002,
    ) -> int:
        """Seed resting bid/ask depth for demo liquidity. Returns orders placed."""
        if mid_price <= 0 or levels <= 0 or quantity <= 0:
            return 0

        orders_placed = 0
        for level in range(1, levels + 1):
            offset = mid_price * spread_pct * level
            bid = round(max(0.01, mid_price - offset), 2)
            ask = round(mid_price + offset, 2)
            self.submit(
                ticker=ticker,
                side="BUY",
                order_type="LIMIT",
                price=bid,
                quantity=quantity,
                bot_id="liquidity-seed",
            )
            orders_placed += 1
            self.submit(
                ticker=ticker,
                side="SELL",
                order_type="LIMIT",
                price=ask,
                quantity=quantity,
                bot_id="liquidity-seed",
            )
            orders_placed += 1
        return orders_placed

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_or_create_book(self, ticker: str):
        if ticker not in self._books:
            self._books[ticker] = self._engine.OrderBook()
        return self._books[ticker]

    def _extract_fills(
        self,
        ticker:         str,
        side:           str,
        order_id:       int,
        quantity:       int,
        price:          float,
        trades_before:  int,
        trades_after:   int,
        book,
    ) -> list[FillRecord]:
        """
        Derive fills using getTrades(since_index) — returns only trades that
        resulted from the order just submitted.
        """
        if trades_after <= trades_before:
            return []

        new_trades = book.getTrades(trades_before)
        fills = []
        for trade in new_trades:
            # Determine which order_id from this submission matched
            matched_id    = (trade.buy_order_id  if side == "BUY"
                             else trade.sell_order_id)
            effective_qty = trade.quantity
            fill_price    = trade.price
            fills.append(FillRecord(
                order_id=matched_id,
                ticker=ticker,
                side=side,
                quantity=effective_qty,
                price=fill_price,
            ))
        return fills
