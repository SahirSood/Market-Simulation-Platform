"""Run a historical replay from a JSON event file.

Example:
    python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db

Event file formats:
    [{"timestamp": "...", "prices": {"AAPL": 190.0}, "recent_headlines": [...]}]

or:
    {"name": "Jan replay", "config": {...}, "events": [...]}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
ENGINE_DIR = ROOT / "engine" / "build" / "Debug"
for path in (SIM_DIR, ENGINE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bots import AnalystBot, BearBot, ContrarianBot, DegenBot, MacroBot  # noqa: E402
from engine_adapter import EngineAdapter  # noqa: E402
from news_feed import NewsFeed  # noqa: E402
from price_feed import PriceFeed  # noqa: E402
from rag.repository import RagRepository  # noqa: E402
from replay import AsOfRagRepository, HistoricalReplayRunner, ReplayStore  # noqa: E402
from risk import RiskLimits  # noqa: E402
from model_config import replay_config_snapshot  # noqa: E402


BOT_CLASSES = {
    "bear": BearBot,
    "degen": DegenBot,
    "analyst": AnalystBot,
    "contrarian": ContrarianBot,
    "macro": MacroBot,
}
PROVIDERS = ("claude", "openai")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase D historical replay events.")
    parser.add_argument("--events", required=True, help="Path to replay event JSON.")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///replay.db",
        help="SQLAlchemy database URL for replay/RAG tables.",
    )
    parser.add_argument("--name", default=None, help="Replay run name.")
    parser.add_argument(
        "--providers",
        default="claude,openai",
        help="Comma-separated providers: claude,openai.",
    )
    parser.add_argument(
        "--bots",
        default="bear,degen,analyst,contrarian,macro",
        help="Comma-separated bot names.",
    )
    parser.add_argument(
        "--no-orders",
        action="store_true",
        help="Record decisions and risk checks without submitting orders.",
    )
    parser.add_argument("--notes", default=None, help="Optional run notes.")
    return parser.parse_args()


def load_event_file(path: str) -> tuple[str | None, dict, list[dict]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return None, {}, payload
    if not isinstance(payload, dict):
        raise ValueError("Replay event file must be a JSON list or object.")
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("Replay event object must contain an events list.")
    return payload.get("name"), payload.get("config") or {}, events


def selected_values(raw: str, allowed: set[str], label: str) -> list[str]:
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unknown = [item for item in values if item not in allowed]
    if unknown:
        raise ValueError(f"Unknown {label}: {', '.join(unknown)}")
    return values


def build_bots(price_feed, news_feed, providers, bot_names, rag_repository):
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


def main() -> int:
    args = parse_args()
    file_name, file_config, events = load_event_file(args.events)
    providers = selected_values(args.providers, set(PROVIDERS), "provider")
    bot_names = selected_values(args.bots, set(BOT_CLASSES), "bot")

    price_feed = PriceFeed()
    news_feed = NewsFeed(api_key="replay")
    engine_adapter = EngineAdapter()
    replay_store = ReplayStore(args.db)

    rag_repository = RagRepository(args.db)
    rag_repository.create_tables()

    bots = build_bots(
        price_feed=price_feed,
        news_feed=news_feed,
        providers=providers,
        bot_names=bot_names,
        rag_repository=rag_repository,
    )

    risk_limits = RiskLimits()
    config = {
        **file_config,
        "event_count": len(events),
        "providers": providers,
        "bots": bot_names,
        "execute_orders": not args.no_orders,
        "model_config": replay_config_snapshot(
            bots=bots,
            providers=providers,
            risk_limits=risk_limits,
        ),
    }
    run = replay_store.create_run(
        name=args.name or file_name or Path(args.events).stem,
        config=config,
        input_events=events,
        notes=args.notes,
    )

    runner = HistoricalReplayRunner(
        bots=bots,
        price_feed=price_feed,
        news_feed=news_feed,
        replay_store=replay_store,
        engine_adapter=engine_adapter,
        risk_limits=risk_limits,
        execute_orders=not args.no_orders,
    )

    try:
        decisions = runner.run_events(events, run_id=run["id"])
    except Exception:
        replay_store.complete_run(run["id"], status="failed")
        raise

    replay_store.complete_run(run["id"])
    completed = replay_store.get_run(run["id"])
    print(json.dumps({
        "run_id": run["id"],
        "status": completed["status"] if completed else "completed",
        "decision_count": len(decisions),
        "input_fingerprint": run["input_fingerprint"],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
