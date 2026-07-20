"""Deterministic order risk controls for the simulator.

The scheduler calls this before any non-HOLD order reaches the matching engine.
These checks are intentionally simple and deterministic so they can become the
same contract used by future agent tools and replay/eval runs.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from config import TRADABLE_TICKERS


@dataclass(frozen=True)
class RiskLimits:
    max_order_quantity: int = 250
    max_order_notional: float = 25_000.0
    max_position_quantity: int = 500
    max_position_notional: float = 75_000.0
    min_cash_after_buy: float = 0.0
    allow_short_selling: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RiskCheckResult:
    approved: bool
    reason: str
    action: str
    ticker: Optional[str]
    quantity: Optional[int]
    estimated_price: Optional[float]
    estimated_notional: Optional[float]
    limits: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _reject(
    reason: str,
    action: str,
    ticker: Optional[str],
    quantity: Optional[int],
    estimated_price: Optional[float],
    estimated_notional: Optional[float],
    limits: RiskLimits,
) -> RiskCheckResult:
    return RiskCheckResult(
        approved=False,
        reason=reason,
        action=action,
        ticker=ticker,
        quantity=quantity,
        estimated_price=estimated_price,
        estimated_notional=estimated_notional,
        limits=limits.to_dict(),
    )


def risk_check_order(
    bot,
    decision,
    price_feed,
    limits: Optional[RiskLimits] = None,
) -> RiskCheckResult:
    """Validate one proposed order against deterministic portfolio limits."""
    limits = limits or RiskLimits()
    action = str(getattr(decision, "action", "") or "").upper()
    ticker = getattr(decision, "ticker", None)
    quantity = getattr(decision, "quantity", None)
    limit_price = getattr(decision, "limit_price", None)

    if action == "HOLD":
        return RiskCheckResult(
            approved=True,
            reason="HOLD requires no risk check",
            action=action,
            ticker=ticker,
            quantity=quantity,
            estimated_price=None,
            estimated_notional=None,
            limits=limits.to_dict(),
        )

    if action not in {"BUY", "SELL"}:
        return _reject("invalid action", action, ticker, quantity, None, None, limits)
    if not ticker:
        return _reject("missing ticker", action, ticker, quantity, None, None, limits)
    ticker = str(ticker).upper().strip()
    allowed_tickers = {str(t).upper().strip() for t in TRADABLE_TICKERS}
    if allowed_tickers and ticker not in allowed_tickers:
        return _reject(
            f"ticker {ticker} is outside tradable universe",
            action,
            ticker,
            quantity,
            None,
            None,
            limits,
        )

    try:
        quantity_int = int(quantity)
    except Exception:
        return _reject("quantity must be an integer", action, ticker, quantity, None, None, limits)
    if quantity_int <= 0:
        return _reject("quantity must be positive", action, ticker, quantity_int, None, None, limits)
    if quantity_int > limits.max_order_quantity:
        return _reject(
            f"quantity exceeds max_order_quantity={limits.max_order_quantity}",
            action,
            ticker,
            quantity_int,
            None,
            None,
            limits,
        )

    try:
        estimated_price = float(limit_price) if limit_price is not None else float(price_feed.get_price(ticker))
    except Exception as exc:
        return _reject(f"price unavailable: {exc}", action, ticker, quantity_int, None, None, limits)
    if estimated_price <= 0:
        return _reject("price must be positive", action, ticker, quantity_int, estimated_price, None, limits)

    estimated_notional = estimated_price * quantity_int
    if estimated_notional > limits.max_order_notional:
        return _reject(
            f"order notional exceeds max_order_notional={limits.max_order_notional:.2f}",
            action,
            ticker,
            quantity_int,
            estimated_price,
            estimated_notional,
            limits,
        )

    snapshot = bot.portfolio.snapshot()
    cash = float(snapshot.get("cash", 0.0))
    current_qty = int(snapshot.get("positions", {}).get(ticker, 0))

    if action == "BUY":
        if cash - estimated_notional < limits.min_cash_after_buy:
            return _reject(
                "insufficient cash after buy",
                action,
                ticker,
                quantity_int,
                estimated_price,
                estimated_notional,
                limits,
            )
        projected_qty = current_qty + quantity_int
        if projected_qty > limits.max_position_quantity:
            return _reject(
                f"position quantity would exceed max_position_quantity={limits.max_position_quantity}",
                action,
                ticker,
                quantity_int,
                estimated_price,
                estimated_notional,
                limits,
            )
        if projected_qty * estimated_price > limits.max_position_notional:
            return _reject(
                f"position notional would exceed max_position_notional={limits.max_position_notional:.2f}",
                action,
                ticker,
                quantity_int,
                estimated_price,
                estimated_notional,
                limits,
            )

    if action == "SELL" and not limits.allow_short_selling and quantity_int > current_qty:
        return _reject(
            f"short selling disabled; held quantity={current_qty}",
            action,
            ticker,
            quantity_int,
            estimated_price,
            estimated_notional,
            limits,
        )

    return RiskCheckResult(
        approved=True,
        reason="approved",
        action=action,
        ticker=ticker,
        quantity=quantity_int,
        estimated_price=estimated_price,
        estimated_notional=estimated_notional,
        limits=limits.to_dict(),
    )
