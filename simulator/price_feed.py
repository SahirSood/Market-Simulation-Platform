import threading
import time

import yfinance as yf

from config import PRICE_CACHE_TTL, TRADABLE_TICKERS


class PriceFeedError(Exception):
    pass


class PriceFeed:
    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._tradable_tickers: set[str] = {ticker.upper() for ticker in TRADABLE_TICKERS}
        self._lock = threading.RLock()

    def _fetch(self, ticker: str) -> None:
        """Fetch fresh price + OHLCV from yfinance and store in cache."""
        symbol = ticker.upper().strip()
        t = yf.Ticker(symbol)
        fi = t.fast_info

        price = fi.last_price
        if price is None:
            raise PriceFeedError(f"yfinance returned None price for {symbol}")

        ohlcv = {
            "open": getattr(fi, "open", None),
            "high": getattr(fi, "day_high", None),
            "low": getattr(fi, "day_low", None),
            "close": getattr(fi, "previous_close", None),
            "volume": getattr(fi, "three_month_average_volume", None),
        }

        with self._lock:
            self._cache[symbol] = {
                "price": price,
                "ohlcv": ohlcv,
                "timestamp": time.time(),
            }

    def _is_stale(self, ticker: str) -> bool:
        """Return True if cache entry is missing or older than PRICE_CACHE_TTL."""
        symbol = ticker.upper().strip()
        with self._lock:
            if symbol not in self._cache:
                return True
            return (time.time() - self._cache[symbol]["timestamp"]) > PRICE_CACHE_TTL

    def get_price(self, ticker: str) -> float:
        """Return current price for any ticker. Fetches fresh if cache is stale."""
        symbol = ticker.upper().strip()
        if self._is_stale(symbol):
            try:
                self._fetch(symbol)
            except Exception as e:
                with self._lock:
                    if symbol in self._cache:
                        return self._cache[symbol]["price"]
                raise PriceFeedError(f"Failed to fetch price for {symbol}: {e}") from e
        with self._lock:
            return self._cache[symbol]["price"]

    def get_ohlcv(self, ticker: str) -> dict:
        """Return {open, high, low, close, volume} for today. Shares cache with get_price."""
        symbol = ticker.upper().strip()
        if self._is_stale(symbol):
            try:
                self._fetch(symbol)
            except Exception as e:
                with self._lock:
                    if symbol in self._cache:
                        return self._cache[symbol]["ohlcv"]
                raise PriceFeedError(f"Failed to fetch OHLCV for {symbol}: {e}") from e
        with self._lock:
            return self._cache[symbol]["ohlcv"]

    def get_active_tickers(self) -> list[str]:
        """Return all tickers that have been fetched this session."""
        with self._lock:
            return list(self._cache.keys())

    def get_tradable_tickers(self) -> list[str]:
        """Return configured tickers plus any researched additions."""
        with self._lock:
            return sorted(self._tradable_tickers)

    def add_tradable_ticker(self, ticker: str) -> bool:
        """Add a researched ticker to the live universe for later bot cycles."""
        symbol = str(ticker or "").upper().strip()
        if not symbol:
            return False
        with self._lock:
            before = len(self._tradable_tickers)
            self._tradable_tickers.add(symbol)
            return len(self._tradable_tickers) > before
