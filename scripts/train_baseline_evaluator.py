"""Train a lightweight baseline evaluator from an exported ML CSV."""
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

from baseline_model import DEFAULT_FEATURE_COLUMNS, train_baseline_from_csv  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a baseline model on replay ML rows.")
    parser.add_argument("--dataset", required=True, help="CSV dataset from export_ml_dataset.py.")
    parser.add_argument(
        "--target",
        default="directional_correct_next_event",
        help="Binary target column.",
    )
    parser.add_argument(
        "--model",
        default="logistic_regression",
        choices=["logistic_regression"],
        help="Baseline model type.",
    )
    parser.add_argument(
        "--features",
        default=None,
        help="Comma-separated feature columns. Defaults to leakage-safe v1 features.",
    )
    parser.add_argument("--time-column", default="as_of_time", help="Timestamp column for time split.")
    parser.add_argument("--report", required=True, help="JSON report output path.")
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=0.001)
    parser.add_argument("--min-rows", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    features = (
        [part.strip() for part in args.features.split(",") if part.strip()]
        if args.features
        else DEFAULT_FEATURE_COLUMNS
    )
    report = train_baseline_from_csv(
        dataset_path=args.dataset,
        target=args.target,
        report_path=args.report,
        feature_columns=features,
        time_column=args.time_column,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
        min_rows=args.min_rows,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
