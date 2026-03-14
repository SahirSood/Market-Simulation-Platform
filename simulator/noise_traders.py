"""
Noise traders — lightweight market participants that keep the order book liquid.

10 RandomTraders place small random limit orders around the current mid-price
on a configurable interval. No LLM calls, no news feed, no personality.
They are invisible to the UI — pure infrastructure to ensure the 5 AI bots
always have a counterparty.
"""
import random
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fallback ticker pool used before the price feed has cached anything
_DEFAULT_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA",
                    "SPY",  "QQQ",  "TLT",  "GLD",   "IEF",
                    "AMZN", "META", "NFLX", "AMD",   "INTC"]


@dataclass
class NoiseConfig:
    spread_pct:  float = 0.002  # place orders within 0.2% of mid-price
    qty_min:     int   = 10
    qty_max:     int   = 100
    cancel_prob: float = 0.30   # 30% chance to cancel previous resting order each cycle


class RandomTrader:
    """
    A single noise-trading agent.
    Places one random limit order per call to act(), and optionally
    cancels its previous resting order first.
    """

    def __init__(
        self,
        trader_id:      int,
        price_feed,
        engine_adapter,
        config: NoiseConfig = None,
    ):
        self.trader_id      = trader_id
        self.price_feed     = price_feed
        self.engine_adapter = engine_adapter
        self.config         = config or NoiseConfig()
        self._active_order_id: int | None = None

    def act(self) -> None:
        # Use whatever tickers the price feed has already priced (i.e. what bots are trading).
        # Fall back to a broad default set on first run before any bot has traded.
        active = self.price_feed.get_active_tickers()
        ticker = random.choice(active if active else _DEFAULT_TICKERS)

        try:
            mid = self.price_feed.get_price(ticker)
        except Exception as e:
            logger.warning(f"[NoiseTrader-{self.trader_id}] Price feed error for {ticker}: {e}")
            return

        # Optionally cancel the previous resting order
        if self._active_order_id is not None:
            if random.random() < self.config.cancel_prob:
                self.engine_adapter.cancel(self._active_order_id)
                self._active_order_id = None

        side     = random.choice(["BUY", "SELL"])
        spread   = mid * self.config.spread_pct
        offset   = random.uniform(0, spread)
        price    = round((mid - offset) if side == "BUY" else (mid + offset), 2)
        quantity = random.randint(self.config.qty_min, self.config.qty_max)

        try:
            order_id, _fills = self.engine_adapter.submit(
                ticker=ticker,
                side=side,
                order_type="LIMIT",
                price=price,
                quantity=quantity,
                bot_id=f"noise-{self.trader_id}",
            )
            self._active_order_id = order_id
            logger.debug(
                f"[NoiseTrader-{self.trader_id}] {side} {quantity} {ticker} @ {price:.2f}"
            )
        except Exception as e:
            logger.warning(f"[NoiseTrader-{self.trader_id}] submit failed: {e}")


class NoiseTraderPool:
    """
    Manages a pool of RandomTraders. Called by BotScheduler every NOISE_INTERVAL.
    """

    def __init__(self, price_feed, engine_adapter, n_traders: int = 10):
        self._traders = [
            RandomTrader(i, price_feed, engine_adapter)
            for i in range(n_traders)
        ]

    def tick(self) -> None:
        """Activate all traders once. Any individual error is caught and logged."""
        for trader in self._traders:
            try:
                trader.act()
            except Exception as e:
                logger.error(
                    f"[NoiseTraderPool] Unhandled error in trader {trader.trader_id}: {e}"
                )

    @property
    def trader_count(self) -> int:
        return len(self._traders)
