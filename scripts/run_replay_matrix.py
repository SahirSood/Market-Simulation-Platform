"""Run replay fixtures across provider sets for same-input comparisons."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = ROOT / "data" / "replay_events"
SUCCESS_STATUSES = {"completed", "succeeded"}
FAILED_STATUSES = {"failed"}


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
    parser.add_argument("--continue-on-error", action="store_true", help="Run remaining commands after a failure.")
    parser.add_argument("--report", default=None, help="Optional JSON report path.")
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


def build_report(commands: list[list[str]], results: list[dict] | None = None, *, dry_run: bool = False) -> dict:
    rows = results
    if rows is None:
        rows = [{"command": _public_command(command), "status": "planned"} for command in commands]
    else:
        rows = [
            {**row, "command": _public_command(row.get("command") or [])}
            for row in rows
        ]
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dry_run": dry_run,
        "command_count": len(commands),
        "succeeded": sum(1 for row in rows if _row_succeeded(row)),
        "failed": sum(1 for row in rows if _row_failed(row)),
        "runs": rows,
    }


def _row_succeeded(row: dict) -> bool:
    if row.get("returncode") is not None:
        return row.get("returncode") == 0
    return row.get("status") in SUCCESS_STATUSES


def _row_failed(row: dict) -> bool:
    if row.get("returncode") is not None:
        return row.get("returncode") != 0
    return row.get("status") in FAILED_STATUSES


def _public_command(command: list[str]) -> list[str]:
    sanitized = [str(part) for part in command]
    for index, part in enumerate(sanitized[:-1]):
        if part == "--db":
            sanitized[index + 1] = "<redacted DATABASE_URL>"
    return sanitized


def _parse_replay_stdout(stdout: str | None) -> dict:
    text = str(stdout or "").strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return {
        key: payload.get(key)
        for key in ("run_id", "status", "decision_count", "input_fingerprint")
        if key in payload
    }


def write_report(path: str | Path, report: dict) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def main() -> int:
    args = parse_args()
    commands = build_commands(args)
    if args.dry_run:
        report = build_report(commands, dry_run=True)
        if args.report:
            write_report(args.report, report)
        print(json.dumps(report, indent=2))
        return 0

    results = []
    for command in commands:
        started_at = datetime.utcnow().isoformat() + "Z"
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
        if completed.stderr:
            print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr)
        row = {
            "command": command,
            "status": "succeeded" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat() + "Z",
            **_parse_replay_stdout(completed.stdout),
        }
        if completed.returncode != 0 and completed.stderr:
            row["stderr_excerpt"] = completed.stderr.strip()[:1200]
        results.append(row)
        if completed.returncode != 0 and not args.continue_on_error:
            break

    report = build_report(commands, results)
    if args.report:
        write_report(args.report, report)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
