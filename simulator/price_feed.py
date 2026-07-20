import time
import yfinance as yf
from config import PRICE_CACHE_TTL, TRADABLE_TICKERS


class PriceFeedError(Exception):
    pass


class PriceFeed:
    def __init__(self):
        # WHY: Single cache entry per ticker holds both price and ohlcv — avoids a double network
        # call if a caller asks for both within the same TTL window.
        self._cache: dict[str, dict] = {}

    def _fetch(self, ticker: str) -> None:
        """Fetch fresh price + OHLCV from yfinance and store in cache."""
        t = yf.Ticker(ticker)
        fi = t.fast_info  # lightweight call — avoids pulling full company metadata

        price = fi.last_price
        if price is None:
            raise PriceFeedError(f"yfinance returned None price for {ticker}")

        # fast_info exposes today's OHLCV via separate attributes
        ohlcv = {
            "open":   getattr(fi, "open",            None),
            "high":   getattr(fi, "day_high",        None),
            "low":    getattr(fi, "day_low",         None),
            "close":  getattr(fi, "previous_close",  None),
            "volume": getattr(fi, "three_month_average_volume", None),
        }

        self._cache[ticker] = {
            "price":     price,
            "ohlcv":     ohlcv,
            "timestamp": time.time(),
        }

    def _is_stale(self, ticker: str) -> bool:
        """Return True if cache entry is missing or older than PRICE_CACHE_TTL."""
        if ticker not in self._cache:
            return True
        return (time.time() - self._cache[ticker]["timestamp"]) > PRICE_CACHE_TTL

    def get_price(self, ticker: str) -> float:
        """Return current price for any ticker. Fetches fresh if cache is stale."""
        if self._is_stale(ticker):
            try:
                self._fetch(ticker)
            except Exception as e:
                if ticker in self._cache:
                    # Return last known price rather than crashing — stale is better than nothing
                    return self._cache[ticker]["price"]
                raise PriceFeedError(f"Failed to fetch price for {ticker}: {e}") from e
        return self._cache[ticker]["price"]

    def get_ohlcv(self, ticker: str) -> dict:
        """Return {open, high, low, close, volume} for today. Shares cache with get_price."""
        if self._is_stale(ticker):
            try:
                self._fetch(ticker)
            except Exception as e:
                if ticker in self._cache:
                    return self._cache[ticker]["ohlcv"]
                raise PriceFeedError(f"Failed to fetch OHLCV for {ticker}: {e}") from e
        return self._cache[ticker]["ohlcv"]

    def get_active_tickers(self) -> list[str]:
        """Return all tickers that have been fetched this session."""
        return list(self._cache.keys())

    def get_tradable_tickers(self) -> list[str]:
        """Return the configured ticker universe bots are allowed to trade."""
        return list(TRADABLE_TICKERS)
