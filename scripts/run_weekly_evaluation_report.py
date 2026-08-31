"""Generate the no-LLM weekly live evaluation report."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import (  # noqa: E402
    BENCHMARK_TICKERS,
    DATABASE_URL,
    LIVE_EVALUATION_REPORT_DIR,
    LIVE_EVALUATION_REPORT_HORIZON,
    LIVE_EVALUATION_REPORT_LOOKBACK_DAYS,
    LIVE_EVALUATION_REPORT_MIN_SAMPLES,
    TRADABLE_TICKERS,
)
from live_evaluation import generate_live_evaluation_report, write_live_evaluation_report  # noqa: E402
from reasoning_log import ReasoningLog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DATABASE_URL, help="SQLAlchemy database URL")
    parser.add_argument("--period-days", type=int, default=LIVE_EVALUATION_REPORT_LOOKBACK_DAYS)
    parser.add_argument("--min-samples", type=int, default=LIVE_EVALUATION_REPORT_MIN_SAMPLES)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument(
        "--horizon",
        choices=("immediate", "1h", "6h", "1d", "7d", "all"),
        default=LIVE_EVALUATION_REPORT_HORIZON,
    )
    parser.add_argument("--since", help="ISO-8601 window start")
    parser.add_argument("--until", help="ISO-8601 window end")
    parser.add_argument("--output-dir", default=LIVE_EVALUATION_REPORT_DIR)
    parser.add_argument("--basename", default=None)
    args = parser.parse_args()

    if not args.db:
        parser.error("--db is required when DATABASE_URL is not configured")
    since = _parse_datetime(args.since) if args.since else None
    until = _parse_datetime(args.until) if args.until else None
    reasoning_log = ReasoningLog(args.db)
    report = generate_live_evaluation_report(
        reasoning_log,
        since=since,
        until=until,
        period_days=args.period_days,
        min_samples=args.min_samples,
        decision_limit=args.limit,
        horizon=args.horizon,
        universe=TRADABLE_TICKERS,
        benchmarks=BENCHMARK_TICKERS,
        include_markdown=True,
    )
    paths = write_live_evaluation_report(
        report,
        args.output_dir,
        basename=args.basename,
    )
    print(json.dumps({
        "status": "succeeded",
        "mode": report["mode"],
        "horizon": report["outcomes"]["selected_horizon"],
        "sample": report["sample"],
        **paths,
    }, indent=2))
    return 0


def _parse_datetime(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"Invalid ISO-8601 datetime: {value}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
