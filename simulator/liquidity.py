import logging

from config import (
    SEED_LIQUIDITY_LEVELS,
    SEED_LIQUIDITY_ON_STARTUP,
    SEED_LIQUIDITY_QTY,
    SEED_LIQUIDITY_SPREAD_PCT,
    TRADABLE_TICKERS,
)

logger = logging.getLogger(__name__)


def seed_order_book_liquidity(price_feed, engine_adapter) -> list[dict]:
    """Seed bid/ask depth for the configured demo ticker universe."""
    if not SEED_LIQUIDITY_ON_STARTUP:
        return []

    seeded: list[dict] = []
    for ticker in TRADABLE_TICKERS:
        try:
            mid = float(price_feed.get_price(ticker))
            orders = engine_adapter.seed_liquidity(
                ticker=ticker,
                mid_price=mid,
                levels=SEED_LIQUIDITY_LEVELS,
                quantity=SEED_LIQUIDITY_QTY,
                spread_pct=SEED_LIQUIDITY_SPREAD_PCT,
            )
            seeded.append({"ticker": ticker, "mid_price": mid, "orders": orders})
        except Exception as exc:
            logger.warning("Liquidity seed skipped for %s: %s", ticker, exc)

    if seeded:
        logger.info(
            "Seeded demo liquidity for %s tickers: %s",
            len(seeded),
            ", ".join(row["ticker"] for row in seeded),
        )
    else:
        logger.warning("No demo liquidity was seeded")
    return seeded
