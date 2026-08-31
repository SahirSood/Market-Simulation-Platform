"""Train the multi-model replay research suite."""
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

from model_suite import DEFAULT_TARGETS, train_model_suite_from_csv  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train multiple tabular models on replay ML rows.")
    parser.add_argument("--dataset", required=True, help="CSV dataset from export_ml_dataset.py.")
    parser.add_argument("--report", required=True, help="JSON report output path.")
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Comma-separated binary target columns.",
    )
    parser.add_argument(
        "--features",
        default=None,
        help="Optional comma-separated feature columns. Defaults to leakage-safe v1 features.",
    )
    parser.add_argument("--time-column", default="as_of_time")
    parser.add_argument("--min-rows", type=int, default=50)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = [part.strip() for part in args.targets.split(",") if part.strip()]
    features = (
        [part.strip() for part in args.features.split(",") if part.strip()]
        if args.features
        else None
    )
    report = train_model_suite_from_csv(
        dataset_path=args.dataset,
        report_path=args.report,
        targets=targets,
        feature_columns=features,
        time_column=args.time_column,
        min_rows=args.min_rows,
        random_state=args.random_state,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
