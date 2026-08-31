"""Export replay decisions to an ML-ready CSV dataset."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ml_dataset import export_replay_ml_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export replay decisions as ML rows.")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///replay.db",
        help="SQLAlchemy database URL for replay tables.",
    )
    parser.add_argument(
        "--mode",
        default="replay",
        choices=["replay"],
        help="Dataset mode. Only replay is implemented for now.",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=[],
        help="Replay run id to include. Can be repeated.",
    )
    parser.add_argument(
        "--input-fingerprint",
        default=None,
        help="Include replay runs with this input fingerprint.",
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Include running/failed runs. Defaults to completed runs only.",
    )
    parser.add_argument("--benchmark", default="SPY", help="Benchmark symbol for relative labels.")
    parser.add_argument(
        "--output",
        required=True,
        help="CSV output path.",
    )
    parser.add_argument(
        "--dictionary",
        default=None,
        help="Optional Markdown feature dictionary path.",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Optional JSON summary path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = export_replay_ml_dataset(
        database_url=args.db,
        output_path=args.output,
        dictionary_path=args.dictionary,
        summary_path=args.summary,
        run_ids=args.run_id,
        input_fingerprint=args.input_fingerprint,
        benchmark=args.benchmark,
        include_incomplete=args.include_incomplete,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
