"""Create due outcome labels for logged live decisions.

Example:
    python scripts/update_decision_outcomes.py --horizons 1h,6h --limit 2000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (SIM_DIR,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from outcomes import OUTCOME_HORIZONS, evaluate_due_outcomes  # noqa: E402
from price_feed import PriceFeed  # noqa: E402
from reasoning_log import ReasoningLog  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update decision outcome labels.")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///marketsim.db",
        help="SQLAlchemy database URL for bot_decisions and decision_outcomes.",
    )
    parser.add_argument(
        "--horizons",
        default=",".join(OUTCOME_HORIZONS.keys()),
        help="Comma-separated horizons: 1h,6h,1d,7d.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum recent decisions to scan.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def _parse_horizons(raw: str) -> list[str]:
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def main() -> int:
    args = parse_args()
    reasoning_log = ReasoningLog(database_url=args.db)
    result = evaluate_due_outcomes(
        reasoning_log,
        PriceFeed(),
        horizons=_parse_horizons(args.horizons),
        decision_limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(
            "Decision outcomes: "
            f"created={result['created_count']} "
            f"existing={result['skipped_existing']} "
            f"not_due={result['skipped_not_due']} "
            f"invalid={result['skipped_invalid']}"
        )
        print("Horizons: " + ", ".join(result["horizons"].keys()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
