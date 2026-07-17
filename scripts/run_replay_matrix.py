"""Run replay fixtures across provider sets for same-input comparisons."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = ROOT / "data" / "replay_events"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a replay matrix across providers.")
    parser.add_argument(
        "--events",
        nargs="*",
        default=None,
        help="Replay event files. Defaults to data/replay_events/sample_*.json.",
    )
    parser.add_argument(
        "--provider-sets",
        nargs="+",
        default=["claude", "openai"],
        help="Provider groups passed to run_replay.py, for example: claude openai claude,openai",
    )
    parser.add_argument("--bots", default="analyst,bear,macro", help="Comma-separated bot names.")
    parser.add_argument("--db", default=os.getenv("DATABASE_URL") or "sqlite:///replay.db")
    parser.add_argument("--no-orders", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    return parser.parse_args()


def event_files(raw_paths: list[str] | None) -> list[Path]:
    if raw_paths:
        return [Path(path) for path in raw_paths]
    return sorted(DEFAULT_EVENTS.glob("sample_*.json"))


def build_commands(args: argparse.Namespace) -> list[list[str]]:
    commands = []
    for event_path in event_files(args.events):
        for providers in args.provider_sets:
            command = [
                sys.executable,
                str(ROOT / "scripts" / "run_replay.py"),
                "--events",
                str(event_path),
                "--providers",
                providers,
                "--bots",
                args.bots,
                "--db",
                args.db,
                "--name",
                f"{event_path.stem} [{providers}]",
                "--notes",
                "replay matrix run",
            ]
            if args.no_orders:
                command.append("--no-orders")
            commands.append(command)
    return commands


def main() -> int:
    args = parse_args()
    commands = build_commands(args)
    if args.dry_run:
        print(json.dumps({"commands": commands}, indent=2))
        return 0
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
