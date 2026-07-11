import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from news_feed import NewsFeed


class FakeResponse:
    def __init__(self, articles):
        self._articles = articles

    def raise_for_status(self):
        return None

    def json(self):
        return {"articles": self._articles}


def _article(title, minutes_old, source="Example"):
    published = datetime.now(timezone.utc) - timedelta(minutes=minutes_old)
    return {
        "title": title,
        "source": {"name": source},
        "publishedAt": published.isoformat().replace("+00:00", "Z"),
        "url": f"https://example.test/{title}",
    }


def test_recent_headlines_are_sorted_by_age(monkeypatch):
    articles = [
        _article("Older", 30),
        _article("Newest", 5),
        _article("Middle", 15),
    ]

    monkeypatch.setattr(
        "news_feed.requests.get",
        lambda *args, **kwargs: FakeResponse(articles),
    )

    feed = NewsFeed(api_key="test")
    recent = feed.get_recent()

    assert [item["title"] for item in recent] == ["Newest", "Middle", "Older"]
    assert [item["age_minutes"] for item in recent] == sorted(
        item["age_minutes"] for item in recent
    )


def test_trending_deduplicates_titles_and_uses_cache_on_failure(monkeypatch):
    calls = {"count": 0}
    articles = [
        _article("Same headline", 10, source="A"),
        _article("Same headline", 9, source="B"),
        _article("Different headline", 8, source="C"),
    ]

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] <= 2:
            return FakeResponse(articles)
        raise RuntimeError("network down")

    monkeypatch.setattr("news_feed.requests.get", fake_get)

    feed = NewsFeed(api_key="test")
    first = feed.get_trending()
    feed._trending_ts = 0.0
    second = feed.get_trending()

    assert [item["title"] for item in first] == ["Same headline", "Different headline"]
    assert second == first


def test_latest_ticker_headlines_are_cached_per_symbol(monkeypatch):
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append(params["q"])
        return FakeResponse([_article("AAPL earnings", 3)])

    monkeypatch.setattr("news_feed.requests.get", fake_get)

    feed = NewsFeed(api_key="test")
    assert feed.get_latest("aapl")[0]["title"] == "AAPL earnings"
    assert feed.get_latest("AAPL")[0]["title"] == "AAPL earnings"
    assert len(calls) == 1
    assert feed.get_headline_count() == 1
