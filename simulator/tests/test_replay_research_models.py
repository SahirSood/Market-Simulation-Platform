import csv
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_suite import train_model_suite_from_csv
from replay_research import analyze_replay_dataset


def _write_research_dataset(path, rows=60):
    start = datetime(2026, 1, 1, 21)
    fieldnames = [
        "as_of_time",
        "action",
        "bot_name",
        "base_personality",
        "llm_provider",
        "confidence",
        "confidence_bucket",
        "event_risk_regime",
        "event_trend_regime",
        "headline_count",
        "real_headline_count",
        "directional_correct_1d",
        "beat_benchmark_1d",
        "large_loss_1d",
        "high_confidence_wrong_1d",
        "intent_mark_pnl_1d",
        "hold_missed_big_move_1d",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(rows):
            label = 1 if index % 3 else 0
            action = "SELL" if index % 2 else "BUY"
            writer.writerow({
                "as_of_time": (start + timedelta(days=index)).isoformat(),
                "action": action,
                "bot_name": "BearBot (Claude)" if index % 2 else "AnalystBot (OpenAI)",
                "base_personality": "BearBot" if index % 2 else "AnalystBot",
                "llm_provider": "claude" if index % 2 else "openai",
                "confidence": 0.8 if label else 0.3,
                "confidence_bucket": "high" if label else "low",
                "event_risk_regime": "risk_off" if index % 2 else "risk_on",
                "event_trend_regime": "down" if index % 2 else "up",
                "headline_count": 4 + (index % 3),
                "real_headline_count": 4 + (index % 3),
                "directional_correct_1d": label,
                "beat_benchmark_1d": label,
                "large_loss_1d": 1 if not label and index % 5 == 0 else 0,
                "high_confidence_wrong_1d": 0,
                "intent_mark_pnl_1d": 25 if label else -10,
                "hold_missed_big_move_1d": 0,
            })


def test_model_suite_and_replay_research_write_reports(tmp_path):
    dataset = tmp_path / "dataset.csv"
    _write_research_dataset(dataset)

    model_report = tmp_path / "model_suite.json"
    suite = train_model_suite_from_csv(
        dataset_path=dataset,
        report_path=model_report,
        targets=["directional_correct_1d", "beat_benchmark_1d"],
        min_rows=10,
    )

    assert model_report.exists()
    assert suite["targets"]["directional_correct_1d"]["status"] == "ok"
    assert "random_forest" in suite["targets"]["directional_correct_1d"]["models"]

    standings = tmp_path / "standings.json"
    markdown = tmp_path / "report.md"
    analysis = analyze_replay_dataset(
        dataset_path=dataset,
        standings_path=standings,
        markdown_path=markdown,
        model_suite_path=model_report,
    )

    assert standings.exists()
    assert markdown.exists()
    assert analysis["overall"]["decision_count"] == 60
    assert analysis["standings"]["bot_provider"]
    assert "Bot / Provider Standings" in markdown.read_text(encoding="utf-8")
