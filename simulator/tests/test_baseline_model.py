import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from baseline_model import train_baseline_from_csv


def test_train_baseline_from_csv_uses_time_split_and_reports_metrics(tmp_path):
    dataset = tmp_path / "dataset.csv"
    with dataset.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "as_of_time",
                "confidence",
                "llm_provider",
                "base_personality",
                "directional_correct_next_event",
            ],
        )
        writer.writeheader()
        for index in range(30):
            label = index % 2
            writer.writerow({
                "as_of_time": f"2026-01-{index + 1:02d}T21:00:00+00:00",
                "confidence": 0.9 if label else 0.1,
                "llm_provider": "claude" if index % 3 else "openai",
                "base_personality": "AnalystBot" if index % 2 else "BearBot",
                "directional_correct_next_event": label,
            })

    report_path = tmp_path / "report.json"
    report = train_baseline_from_csv(
        dataset_path=dataset,
        target="directional_correct_next_event",
        report_path=report_path,
        feature_columns=["confidence", "llm_provider", "base_personality"],
        epochs=250,
        min_rows=5,
    )

    assert report["status"] == "ok"
    assert report["split"]["train_rows"] == 21
    assert report["metrics"]["test"]["row_count"] == 5
    assert report["metrics"]["test"]["accuracy"] >= 0.8
    assert report["majority_baseline"]["test"]["row_count"] == 5
    assert report["coefficients"]
    assert report_path.exists()


def test_train_baseline_rejects_label_leakage_features(tmp_path):
    dataset = tmp_path / "dataset.csv"
    dataset.write_text(
        "as_of_time,return_next_event,directional_correct_next_event\n"
        "2026-01-01T21:00:00+00:00,0.1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="label/leakage"):
        train_baseline_from_csv(
            dataset_path=dataset,
            target="directional_correct_next_event",
            feature_columns=["return_next_event"],
            min_rows=1,
        )
