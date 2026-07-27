"""
Portfolio tracks each bot's cash, positions, and P&L.

FillRecord is also defined here so both EngineAdapter and Portfolio
can share the type without a circular import.
"""
import time
import threading
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FillRecord:
    """A single execution — may be a partial fill of a larger order."""
    order_id:  int
    ticker:    str
    side:      str          # "BUY" | "SELL"
    quantity:  int
    price:     float
    timestamp: float = field(default_factory=time.time)


class Portfolio:
    """
    Tracks cash, share positions, and cost basis for one bot.
    Thread-safe: a threading.Lock guards all mutations.
    """

    def __init__(self, starting_cash: float, allow_short_selling: bool = False):
        self._starting_cash: float = starting_cash
        self.allow_short_selling: bool = bool(allow_short_selling)
        self.cash:            float = starting_cash
        self.positions:       dict[str, int]   = {}   # signed quantity; negative means short
        self._cost_basis:     dict[str, float] = {}   # average entry price per open position
        self._realized_pnl:   float = 0.0
        self._fills:          list[FillRecord] = []
        self._lock:           threading.Lock   = threading.Lock()

    # ── Mutations ─────────────────────────────────────────────────────────────

    def apply_fill(self, fill: FillRecord, strict: bool = True) -> None:
        """
        Update cash and positions after a confirmed engine fill.

        strict=True  → raise ValueError on overdraft / short-sell (default for real fills)
        strict=False → log warning and continue (for approximate fill data)
        """
        with self._lock:
            if fill.quantity <= 0 or fill.price < 0:
                raise ValueError("Fill quantity must be positive and price cannot be negative")

            if fill.side == "BUY":
                cost = fill.price * fill.quantity
                if cost > self.cash:
                    msg = (f"Insufficient cash: need ${cost:,.2f}, "
                           f"have ${self.cash:,.2f} (order_id={fill.order_id})")
                    if strict:
                        raise ValueError(msg)
                    logger.warning(f"[Portfolio] {msg} — applying anyway (strict=False)")

                prev_qty = self.positions.get(fill.ticker, 0)
                prev_basis = self._cost_basis.get(fill.ticker, fill.price)
                new_qty = prev_qty + fill.quantity
                if prev_qty >= 0:
                    self._cost_basis[fill.ticker] = (
                        (prev_basis * prev_qty + fill.price * fill.quantity) / new_qty
                    )
                    self.positions[fill.ticker] = new_qty
                else:
                    covered = min(fill.quantity, abs(prev_qty))
                    self._realized_pnl += (prev_basis - fill.price) * covered
                    if new_qty < 0:
                        self.positions[fill.ticker] = new_qty
                    elif new_qty == 0:
                        self.positions.pop(fill.ticker, None)
                        self._cost_basis.pop(fill.ticker, None)
                    else:
                        self.positions[fill.ticker] = new_qty
                        self._cost_basis[fill.ticker] = fill.price
                self.cash -= cost

            elif fill.side == "SELL":
                current_qty = self.positions.get(fill.ticker, 0)
                if fill.quantity > max(0, current_qty) and not self.allow_short_selling:
                    msg = (f"Cannot sell {fill.quantity} of {fill.ticker}: "
                           f"only hold {current_qty} (order_id={fill.order_id})")
                    if strict:
                        raise ValueError(msg)
                    logger.warning(f"[Portfolio] {msg} — applying anyway (strict=False)")
                    # Sell only what is held when approximate legacy data is replayed.
                    fill = FillRecord(
                        order_id=fill.order_id, ticker=fill.ticker, side=fill.side,
                        quantity=max(0, current_qty), price=fill.price, timestamp=fill.timestamp,
                    )

                if fill.quantity <= 0:
                    return

                proceeds = fill.price * fill.quantity
                self.cash += proceeds
                current_qty = self.positions.get(fill.ticker, 0)
                current_basis = self._cost_basis.get(fill.ticker, fill.price)
                new_qty = current_qty - fill.quantity
                if current_qty <= 0:
                    prior_short = abs(current_qty)
                    self.positions[fill.ticker] = new_qty
                    self._cost_basis[fill.ticker] = (
                        (current_basis * prior_short + fill.price * fill.quantity)
                        / abs(new_qty)
                    )
                else:
                    closed = min(fill.quantity, current_qty)
                    self._realized_pnl += (fill.price - current_basis) * closed
                    if new_qty > 0:
                        self.positions[fill.ticker] = new_qty
                    elif new_qty == 0:
                        self.positions.pop(fill.ticker, None)
                        self._cost_basis.pop(fill.ticker, None)
                    else:
                        self.positions[fill.ticker] = new_qty
                        self._cost_basis[fill.ticker] = fill.price

            else:
                raise ValueError(f"Unsupported fill side: {fill.side}")

            self._fills.append(fill)

    # ── Read-only queries ──────────────────────────────────────────────────────

    def mark_to_market(self, price_feed) -> float:
        """Total portfolio value: cash + all positions at current market price."""
        with self._lock:
            equity = 0.0
            for ticker, qty in self.positions.items():
                try:
                    equity += price_feed.get_price(ticker) * qty
                except Exception as e:
                    logger.warning(f"[Portfolio] mark_to_market: price fetch failed for {ticker}: {e}")
            return self.cash + equity

    def unrealized_pnl(self, price_feed) -> dict[str, float]:
        """Per-position unrealized P&L: (current_price - avg_cost) * qty."""
        with self._lock:
            result: dict[str, float] = {}
            for ticker, qty in self.positions.items():
                try:
                    current = price_feed.get_price(ticker)
                    basis   = self._cost_basis.get(ticker, current)
                    result[ticker] = (current - basis) * qty
                except Exception as e:
                    logger.warning(f"[Portfolio] unrealized_pnl: price fetch failed for {ticker}: {e}")
                    result[ticker] = 0.0
            return result

    def total_unrealized_pnl(self, price_feed) -> float:
        return sum(self.unrealized_pnl(price_feed).values())

    def realized_pnl(self) -> float:
        """Realized P&L from closed long shares and covered short shares."""
        with self._lock:
            return self._realized_pnl

    def snapshot(self) -> dict:
        """JSON-serializable dict — stored in the reasoning log for audit trail."""
        with self._lock:
            return {
                "cash":       round(self.cash, 2),
                "positions":  dict(self.positions),
                "cost_basis": {k: round(v, 4) for k, v in self._cost_basis.items()},
                "realized_pnl": round(self._realized_pnl, 2),
                "short_selling_enabled": self.allow_short_selling,
            }
