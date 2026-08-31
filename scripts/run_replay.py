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
for path in (ROOT, SIM_DIR, ENGINE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from replay_workflow import BOT_CLASSES, PROVIDERS, run_historical_replay  # noqa: E402


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


def main() -> int:
    args = parse_args()
    file_name, file_config, events = load_event_file(args.events)
    providers = selected_values(args.providers, set(PROVIDERS), "provider")
    bot_names = selected_values(args.bots, set(BOT_CLASSES), "bot")

    result = run_historical_replay(
        database_url=args.db,
        events=events,
        name=args.name or file_name or Path(args.events).stem,
        config=file_config,
        providers=providers,
        bot_names=bot_names,
        execute_orders=not args.no_orders,
        notes=args.notes,
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "status": result["status"],
        "decision_count": result["decision_count"],
        "input_fingerprint": result["input_fingerprint"],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
