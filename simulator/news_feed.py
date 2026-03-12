import time
import logging
from datetime import datetime, timezone
import requests
from config import NEWS_API_KEY, NEWS_CACHE_TTL

logger = logging.getLogger(__name__)

_HEADLINES_URL = "https://newsapi.org/v2/top-headlines"
_EVERYTHING_URL = "https://newsapi.org/v2/everything"


def _parse_age(published_at: str) -> tuple[int, str]:
    """
    Parse ISO 8601 timestamp into (age_minutes, human_label).
    Returns (999, 'unknown') on parse failure.
    """
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
        age_min = int(age_seconds / 60)
        if age_min < 60:
            label = f"{age_min} min ago"
        elif age_min < 1440:
            label = f"{age_min // 60}h ago"
        else:
            label = f"{age_min // 1440}d ago"
        return age_min, label
    except Exception:
        return 999, "unknown"


def _article_to_dict(a: dict) -> dict:
    published_at = a.get("publishedAt", "")
    age_minutes, age_label = _parse_age(published_at)
    return {
        "title":        (a.get("title") or "").strip(),
        "source":       (a.get("source") or {}).get("name", "Unknown"),
        "published_at": published_at,
        "age_minutes":  age_minutes,   # WHY: raw int so bots can filter "only news < 60 min old"
        "age_label":    age_label,     # WHY: human string so LLM reads "12 min ago" not ISO timestamp
        "url":          a.get("url", ""),
    }


class NewsFeed:
    def __init__(self, api_key: str = None):
        self._api_key = api_key or NEWS_API_KEY
        # WHY: separate caches — trending and recent are different API calls with different sort orders
        self._trending_cache: list[dict] = []
        self._recent_cache: list[dict] = []
        self._trending_ts: float = 0.0
        self._recent_ts:   float = 0.0

    def _is_stale(self, ts: float) -> bool:
        return (time.time() - ts) > NEWS_CACHE_TTL

    def _fetch_raw(self, url: str, params: dict) -> list[dict]:
        """Single NewsAPI call, returns list of raw article dicts. Raises on failure."""
        headers = {"X-Api-Key": self._api_key}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("articles", [])

    def _dedup(self, articles: list[dict]) -> list[dict]:
        """Remove articles with duplicate titles."""
        seen: set[str] = set()
        out: list[dict] = []
        for a in articles:
            title = (a.get("title") or "").strip()
            if title and title not in seen:
                seen.add(title)
                out.append(a)
        return out

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def get_trending(self, n: int = 25) -> list[dict]:
        """
        Top finance headlines ranked by popularity/engagement.
        Combines /top-headlines (business) + /everything (sortBy=popularity).
        Good for: macro events, broad market moves, high-impact news.
        """
        if self._is_stale(self._trending_ts):
            raw = []
            for url, params in [
                (_HEADLINES_URL,  {"category": "business", "language": "en", "pageSize": 15}),
                (_EVERYTHING_URL, {"q": "stocks earnings market", "language": "en",
                                   "sortBy": "popularity", "pageSize": 15}),
            ]:
                try:
                    raw += self._fetch_raw(url, params)
                except Exception as e:
                    logger.warning(f"NewsFeed.get_trending: call to {url} failed: {e}")

            fresh = [_article_to_dict(a) for a in self._dedup(raw) if (a.get("title") or "").strip()]
            if fresh:
                self._trending_cache = fresh
                self._trending_ts = time.time()
            elif not self._trending_cache:
                logger.warning("NewsFeed.get_trending: no data and no cache")
                return []
            else:
                logger.warning("NewsFeed.get_trending: API failed — returning stale cache")

        return self._trending_cache[:n]

    def get_recent(self, n: int = 25) -> list[dict]:
        """
        Most recently published finance headlines, newest first.
        Uses /everything sortBy=publishedAt — captures breaking news before it trends.
        Good for: momentum bots reacting to fresh headlines, time-sensitive signals.
        """
        if self._is_stale(self._recent_ts):
            try:
                raw = self._fetch_raw(
                    _EVERYTHING_URL,
                    {"q": "stocks earnings market finance",
                     "language": "en",
                     "sortBy": "publishedAt",
                     "pageSize": 30},
                )
                fresh = [_article_to_dict(a) for a in self._dedup(raw)
                         if (a.get("title") or "").strip()]
                # Sort ascending age so index 0 = newest
                fresh.sort(key=lambda h: h["age_minutes"])
                if fresh:
                    self._recent_cache = fresh
                    self._recent_ts = time.time()
                elif not self._recent_cache:
                    logger.warning("NewsFeed.get_recent: no data and no cache")
                    return []
            except Exception as e:
                logger.warning(f"NewsFeed.get_recent: failed: {e}")
                if not self._recent_cache:
                    return []

        return self._recent_cache[:n]

    def get_headline_count(self) -> int:
        """Total headlines across both caches (for diagnostics)."""
        return len(self._trending_cache) + len(self._recent_cache)
