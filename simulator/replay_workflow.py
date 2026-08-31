"""Reusable helpers for protected API and CLI replay runs."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from bots import AnalystBot, BearBot, ContrarianBot, DegenBot, MacroBot
from engine_adapter import EngineAdapter
from model_config import replay_config_snapshot
from rag.repository import RagRepository
from replay import AsOfRagRepository, HistoricalReplayRunner, ReplayStore
from risk import RiskLimits


BOT_CLASSES = {
    "bear": BearBot,
    "degen": DegenBot,
    "analyst": AnalystBot,
    "contrarian": ContrarianBot,
    "macro": MacroBot,
}
PROVIDERS = ("claude", "openai")
DEFAULT_BOTS = tuple(BOT_CLASSES.keys())
DEFAULT_PROVIDERS = PROVIDERS
REPLAY_EVENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "replay_events"


class ReplayPriceFeed:
    """No-network replay price feed populated by event prices."""

    _SEEDS = {
        "AAPL": 190.0,
        "NVDA": 490.0,
        "MSFT": 420.0,
        "GOOGL": 175.0,
        "TSLA": 180.0,
        "SPY": 510.0,
        "QQQ": 440.0,
        "TLT": 95.0,
        "GLD": 215.0,
        "IEF": 94.0,
    }

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get_price(self, ticker: str) -> float:
        symbol = str(ticker).upper().strip()
        if symbol not in self._cache:
            self._seed(symbol)
        return float(self._cache[symbol]["price"])

    def get_ohlcv(self, ticker: str) -> dict:
        symbol = str(ticker).upper().strip()
        if symbol not in self._cache:
            self._seed(symbol)
        price = float(self._cache[symbol]["price"])
        return self._cache[symbol].get("ohlcv") or {
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 0,
        }

    def get_active_tickers(self) -> list[str]:
        return list(self._cache.keys())

    def _seed(self, symbol: str) -> None:
        price = float(self._SEEDS.get(symbol, 100.0))
        self._cache[symbol] = {
            "price": price,
            "ohlcv": {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 0,
            },
            "timestamp": time.time(),
        }


class ReplayNewsFeed:
    """No-network replay news feed populated by event headlines."""

    def __init__(self):
        self._trending_cache: list[dict] = []
        self._recent_cache: list[dict] = []
        self._trending_ts: float = 0.0
        self._recent_ts: float = 0.0
        self._ticker_cache: dict[str, list[dict]] = {}
        self._ticker_ts: dict[str, float] = {}

    def get_trending(self, n: int = 25) -> list[dict]:
        return self._trending_cache[:n]

    def get_recent(self, n: int = 25) -> list[dict]:
        return self._recent_cache[:n]

    def get_latest(self, ticker: str, n: int = 5) -> list[dict]:
        return self._ticker_cache.get(str(ticker).upper().strip(), [])[:n]


def load_replay_event_file(path: str, root: Path = REPLAY_EVENTS_DIR) -> tuple[str | None, dict, list[dict]]:
    requested = Path(path)
    if requested.is_absolute() or any(part == ".." for part in requested.parts):
        raise ValueError("event_file must be a relative path in data/replay_events")
    resolved = (root / requested).resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents and resolved != root_resolved:
        raise ValueError("event_file must stay under data/replay_events")

    import json

    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        events = payload
        config = {}
        name = None
    elif isinstance(payload, dict):
        events = payload.get("events")
        config = payload.get("config") or {}
        name = payload.get("name")
    else:
        raise ValueError("Replay event file must be a JSON list or object")
    return name, config, validate_replay_events(events)


def selected_values(values: Sequence[str], allowed: set[str], label: str) -> list[str]:
    selected = [str(item).strip().lower() for item in values if str(item).strip()]
    unknown = [item for item in selected if item not in allowed]
    if unknown:
        raise ValueError(f"Unknown {label}: {', '.join(unknown)}")
    if not selected:
        raise ValueError(f"At least one {label} is required")
    return selected


def validate_replay_events(events) -> list[dict]:
    if not isinstance(events, list) or not events:
        raise ValueError("Replay events must be a non-empty list")
    normalized = []
    previous_time = None
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"Replay event {idx} must be an object")
        raw_time = event.get("timestamp") or event.get("as_of_time")
        if not raw_time:
            raise ValueError(f"Replay event {idx} must include timestamp or as_of_time")
        try:
            event_time = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Replay event {idx} has invalid timestamp") from exc
        if previous_time is not None and event_time <= previous_time:
            raise ValueError("Replay events must be sorted by increasing timestamp")
        previous_time = event_time
        normalized.append(dict(event))
    return normalized


def build_replay_bots(
    price_feed,
    news_feed,
    providers: Sequence[str],
    bot_names: Sequence[str],
    rag_repository=None,
):
    bots = []
    for provider in providers:
        for bot_name in bot_names:
            bot_cls = BOT_CLASSES[bot_name]
            bot = bot_cls(
                price_feed,
                news_feed,
                provider,
                rag_repository=AsOfRagRepository(rag_repository) if rag_repository else None,
                embedding_service=None,
            )
            label = "Claude" if provider == "claude" else "OpenAI"
            bot.base_name = bot.name
            bot.name = f"{bot.name} ({label})"
            bot.bot_id = f"{bot.bot_id}-{provider}"
            bots.append(bot)
    return bots


def run_historical_replay(
    *,
    database_url: str,
    events: Iterable[dict],
    name: str,
    config: dict | None = None,
    providers: Sequence[str] = DEFAULT_PROVIDERS,
    bot_names: Sequence[str] = DEFAULT_BOTS,
    execute_orders: bool = False,
    notes: str | None = None,
    replay_store: ReplayStore | None = None,
    rag_repository: RagRepository | None = None,
) -> dict:
    event_list = validate_replay_events(list(events))
    selected_providers = selected_values(providers, set(PROVIDERS), "provider")
    selected_bot_names = selected_values(bot_names, set(BOT_CLASSES), "bot")

    store = replay_store or ReplayStore(database_url)
    repo = rag_repository or RagRepository(database_url)
    repo.create_tables()

    price_feed = ReplayPriceFeed()
    news_feed = ReplayNewsFeed()
    engine_adapter = EngineAdapter()
    risk_limits = RiskLimits()
    bots = build_replay_bots(
        price_feed=price_feed,
        news_feed=news_feed,
        providers=selected_providers,
        bot_names=selected_bot_names,
        rag_repository=repo,
    )
    run_config = {
        **(config or {}),
        "event_count": len(event_list),
        "providers": selected_providers,
        "bots": selected_bot_names,
        "execute_orders": bool(execute_orders),
        "execution_mode": "isolated_replay",
        "model_config": replay_config_snapshot(
            bots=bots,
            providers=selected_providers,
            risk_limits=risk_limits,
        ),
    }
    run = store.create_run(
        name=name,
        config=run_config,
        input_events=event_list,
        notes=notes,
    )
    runner = HistoricalReplayRunner(
        bots=bots,
        price_feed=price_feed,
        news_feed=news_feed,
        replay_store=store,
        engine_adapter=engine_adapter,
        risk_limits=risk_limits,
        execute_orders=bool(execute_orders),
    )

    try:
        decisions = runner.run_events(event_list, run_id=run["id"])
    except Exception:
        store.complete_run(run["id"], status="failed")
        raise

    store.complete_run(run["id"])
    completed = store.get_run(run["id"]) or run
    return {
        "run_id": run["id"],
        "status": completed.get("status", "completed"),
        "decision_count": len(decisions),
        "input_fingerprint": run.get("input_fingerprint"),
        "run": completed,
    }
