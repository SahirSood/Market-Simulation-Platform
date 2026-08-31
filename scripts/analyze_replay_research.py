"""Build replay standings and a human-readable research report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from replay_research import analyze_replay_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze replay ML rows into standings/report artifacts.")
    parser.add_argument("--dataset", required=True, help="CSV dataset from export_ml_dataset.py.")
    parser.add_argument("--standings", required=True, help="JSON standings output path.")
    parser.add_argument("--markdown", required=True, help="Markdown report output path.")
    parser.add_argument("--model-suite", default=None, help="Optional JSON model suite report.")
    parser.add_argument("--benchmark", default="SPY")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = analyze_replay_dataset(
        dataset_path=args.dataset,
        standings_path=args.standings,
        markdown_path=args.markdown,
        model_suite_path=args.model_suite,
        benchmark=args.benchmark,
    )
    print(json.dumps({
        "standings": args.standings,
        "markdown": args.markdown,
        "decision_count": analysis["overall"]["decision_count"],
        "trade_count": analysis["overall"]["trade_count"],
        "directional_accuracy_1d": analysis["overall"]["directional_accuracy_1d"],
        "beat_benchmark_rate_1d": analysis["overall"]["beat_benchmark_rate_1d"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
