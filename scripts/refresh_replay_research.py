"""Refresh replay ML, model, standings, and report artifacts.

This command does not call LLM providers. It consumes completed replay runs and
regenerates the cheap analysis layer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ml_dataset import export_replay_ml_dataset  # noqa: E402
from model_suite import DEFAULT_TARGETS, train_model_suite_from_csv  # noqa: E402
from replay_research import analyze_replay_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh replay research artifacts from completed replay runs.")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///replay.db",
        help="SQLAlchemy database URL for replay tables.",
    )
    parser.add_argument("--input-fingerprint", default=None, help="Replay input fingerprint to include.")
    parser.add_argument("--run-id", action="append", default=[], help="Replay run id to include. Can repeat.")
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--output-dir", default="data/ml", help="Root output directory.")
    parser.add_argument("--version", default="v2", help="Artifact version suffix.")
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    parser.add_argument("--min-rows", type=int, default=50)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    dataset_dir = output_dir / "datasets"
    report_dir = output_dir / "reports"
    version = args.version.strip() or "v2"

    dataset_path = dataset_dir / f"replay_decisions_{version}.csv"
    summary_path = dataset_dir / f"replay_decisions_{version}.summary.json"
    dictionary_path = dataset_dir / f"feature_dictionary_{version}.md"
    model_suite_path = report_dir / f"model_suite_{version}.json"
    standings_path = report_dir / f"replay_standings_{version}.json"
    markdown_path = report_dir / f"replay_research_report_{version}.md"
    manifest_path = report_dir / f"refresh_manifest_{version}.json"

    summary = export_replay_ml_dataset(
        database_url=args.db,
        output_path=dataset_path,
        dictionary_path=dictionary_path,
        summary_path=summary_path,
        run_ids=args.run_id,
        input_fingerprint=args.input_fingerprint,
        benchmark=args.benchmark,
    )
    targets = [part.strip() for part in args.targets.split(",") if part.strip()]
    model_suite = train_model_suite_from_csv(
        dataset_path=dataset_path,
        report_path=model_suite_path,
        targets=targets,
        min_rows=args.min_rows,
    )
    analysis = analyze_replay_dataset(
        dataset_path=dataset_path,
        standings_path=standings_path,
        markdown_path=markdown_path,
        model_suite_path=model_suite_path,
        benchmark=args.benchmark,
    )
    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "db": _redact_db(args.db),
        "input_fingerprint": args.input_fingerprint,
        "run_ids": args.run_id,
        "benchmark": args.benchmark,
        "version": version,
        "artifacts": {
            "dataset": str(dataset_path),
            "summary": str(summary_path),
            "feature_dictionary": str(dictionary_path),
            "model_suite": str(model_suite_path),
            "standings": str(standings_path),
            "markdown_report": str(markdown_path),
            "manifest": str(manifest_path),
        },
        "summary": {
            "row_count": summary.get("row_count"),
            "trade_row_count": summary.get("trade_row_count"),
            "directional_accuracy": summary.get("directional_accuracy"),
            "beat_benchmark_rate": summary.get("beat_benchmark_rate"),
            "model_targets": list(model_suite.get("targets", {}).keys()),
            "standings_decision_count": analysis["overall"]["decision_count"],
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps(manifest, indent=2, default=str))
    return 0


def _redact_db(value: str) -> str:
    if "://" not in value:
        return value
    prefix, _rest = value.split("://", 1)
    if "@" in _rest:
        return f"{prefix}://<redacted>"
    return value


if __name__ == "__main__":
    raise SystemExit(main())
