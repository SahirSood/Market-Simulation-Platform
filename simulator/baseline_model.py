"""Lightweight baseline models for replay ML datasets.

This is deliberately small and dependency-free. It is meant to establish a
repeatable baseline before adding heavier tabular ML tooling.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_FEATURE_COLUMNS = [
    "action",
    "bot_name",
    "base_personality",
    "llm_provider",
    "confidence",
    "confidence_bucket",
    "speculative",
    "evidence_count",
    "evidence_url_count",
    "risk_checked",
    "risk_approved",
    "headline_count",
    "real_headline_count",
    "synthetic_headline_count",
    "ticker_headline_count",
    "macro_headline_count",
    "filing_headline_count",
    "earnings_headline_count",
    "headline_source_count",
    "has_real_news",
    "has_synthetic_market_summary",
    "news_context_quality",
    "event_spy_return_1d",
    "event_qqq_return_1d",
    "event_tlt_return_1d",
    "event_gld_return_1d",
    "event_risk_regime",
    "event_trend_regime",
    "event_volatility_regime",
    "event_breadth_proxy",
    "ticker_return_1d",
    "ticker_return_5d",
    "ticker_return_20d",
    "ticker_rolling_volatility_20d",
    "ticker_volume_ratio_20d",
    "ticker_gap_from_previous_close",
    "ticker_distance_from_20d_ma",
]

LABEL_LIKE_COLUMNS = {
    "llm_input_tokens",
    "llm_output_tokens",
    "llm_total_tokens",
    "llm_estimated_cost_usd",
    "next_event_price",
    "return_next_event",
    "signed_return_next_event",
    "directional_correct_next_event",
    "intent_mark_pnl_next_event",
    "benchmark_next_event_price",
    "benchmark_return_next_event",
    "excess_return_vs_benchmark_next_event",
    "beat_benchmark_next_event",
    "future_price_1d",
    "future_return_1d",
    "future_signed_return_1d",
    "directional_correct_1d",
    "profitable_1d",
    "intent_mark_pnl_1d",
    "benchmark_future_price_1d",
    "benchmark_return_1d",
    "excess_return_vs_benchmark_1d",
    "beat_benchmark_1d",
    "large_loss_1d",
    "high_confidence_wrong_1d",
    "future_price_3d",
    "future_return_3d",
    "future_signed_return_3d",
    "directional_correct_3d",
    "profitable_3d",
    "intent_mark_pnl_3d",
    "benchmark_future_price_3d",
    "benchmark_return_3d",
    "excess_return_vs_benchmark_3d",
    "beat_benchmark_3d",
    "large_loss_3d",
    "high_confidence_wrong_3d",
    "future_price_7d",
    "future_return_7d",
    "future_signed_return_7d",
    "directional_correct_7d",
    "profitable_7d",
    "intent_mark_pnl_7d",
    "benchmark_future_price_7d",
    "benchmark_return_7d",
    "excess_return_vs_benchmark_7d",
    "beat_benchmark_7d",
    "large_loss_7d",
    "high_confidence_wrong_7d",
    "event_best_long_ticker_1d",
    "event_best_long_return_1d",
    "event_worst_ticker_1d",
    "event_worst_return_1d",
    "event_best_abs_ticker_1d",
    "event_best_abs_return_1d",
    "hold_missed_big_move_1d",
}


def train_baseline_from_csv(
    *,
    dataset_path: str | Path,
    target: str,
    report_path: str | Path | None = None,
    feature_columns: Optional[Iterable[str]] = None,
    time_column: str = "as_of_time",
    train_ratio: float = 0.7,
    validation_ratio: float = 0.15,
    epochs: int = 400,
    learning_rate: float = 0.1,
    l2: float = 0.001,
    min_rows: int = 20,
) -> dict:
    rows = load_dataset_rows(dataset_path)
    features = list(feature_columns or DEFAULT_FEATURE_COLUMNS)
    _validate_features(features, target)
    usable = _usable_rows(rows, target)
    usable.sort(key=lambda row: _timestamp_sort(row.get(time_column)))

    report = train_logistic_baseline(
        usable,
        target=target,
        feature_columns=features,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        epochs=epochs,
        learning_rate=learning_rate,
        l2=l2,
        min_rows=min_rows,
    )
    report.update({
        "dataset": str(dataset_path),
        "target": target,
        "time_column": time_column,
        "feature_columns": features,
        "input_row_count": len(rows),
        "usable_row_count": len(usable),
    })
    if report_path:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def load_dataset_rows(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def train_logistic_baseline(
    rows: list[dict],
    *,
    target: str,
    feature_columns: list[str],
    train_ratio: float = 0.7,
    validation_ratio: float = 0.15,
    epochs: int = 400,
    learning_rate: float = 0.1,
    l2: float = 0.001,
    min_rows: int = 20,
) -> dict:
    warnings = []
    if len(rows) < min_rows:
        warnings.append(
            f"Only {len(rows)} usable rows are available; treat this as exploratory."
        )
    labels = [_target_value(row.get(target)) for row in rows]
    label_counts = Counter(labels)
    if len(label_counts) < 2:
        return {
            "model": "constant_baseline",
            "status": "insufficient_label_diversity",
            "warnings": [*warnings, "Target has only one class."],
            "label_counts": _string_key_counts(label_counts),
        }

    encoder = FeatureEncoder(feature_columns)
    split = _time_split(rows, train_ratio, validation_ratio)
    train_rows = split["train"]
    train_y = [_target_value(row.get(target)) for row in train_rows]
    encoder.fit(train_rows)
    train_x = encoder.transform(train_rows)
    weights = _fit_logistic(
        train_x,
        train_y,
        epochs=epochs,
        learning_rate=learning_rate,
        l2=l2,
    )

    report = {
        "model": "logistic_regression_sgd",
        "status": "ok",
        "warnings": warnings,
        "label_counts": _string_key_counts(label_counts),
        "split": {
            "train_rows": len(split["train"]),
            "validation_rows": len(split["validation"]),
            "test_rows": len(split["test"]),
            "train_ratio": train_ratio,
            "validation_ratio": validation_ratio,
            "method": "time_ordered",
        },
        "metrics": {},
        "majority_baseline": {},
        "coefficients": _top_coefficients(weights, encoder.feature_names),
        "training": {
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
        },
    }

    majority_class = Counter(train_y).most_common(1)[0][0]
    for name, part_rows in split.items():
        y_true = [_target_value(row.get(target)) for row in part_rows]
        x_part = encoder.transform(part_rows)
        probabilities = _predict_probabilities(x_part, weights)
        predictions = [1 if prob >= 0.5 else 0 for prob in probabilities]
        report["metrics"][name] = _classification_metrics(y_true, predictions, probabilities)
        majority_predictions = [majority_class for _ in y_true]
        report["majority_baseline"][name] = _classification_metrics(
            y_true,
            majority_predictions,
            [float(majority_class) for _ in y_true],
        )
    return report


class FeatureEncoder:
    def __init__(self, feature_columns: list[str]):
        self.feature_columns = feature_columns
        self.numeric_columns: list[str] = []
        self.categorical_columns: list[str] = []
        self.numeric_stats: dict[str, tuple[float, float]] = {}
        self.categories: dict[str, list[str]] = {}
        self.feature_names: list[str] = []

    def fit(self, rows: list[dict]) -> None:
        self.numeric_columns = []
        self.categorical_columns = []
        for column in self.feature_columns:
            values = [row.get(column) for row in rows if str(row.get(column) or "").strip()]
            numeric_values = [_to_float(value) for value in values]
            numeric_count = sum(value is not None for value in numeric_values)
            if values and numeric_count == len(values):
                self.numeric_columns.append(column)
            else:
                self.categorical_columns.append(column)

        for column in self.numeric_columns:
            values = [
                _to_float(row.get(column))
                for row in rows
                if _to_float(row.get(column)) is not None
            ]
            mean = sum(values) / len(values) if values else 0.0
            variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
            stdev = math.sqrt(variance) or 1.0
            self.numeric_stats[column] = (mean, stdev)

        for column in self.categorical_columns:
            counter = Counter(
                str(row.get(column) or "<missing>")
                for row in rows
            )
            self.categories[column] = [
                value for value, _count in counter.most_common(25)
            ]

        self.feature_names = ["bias"]
        for column in self.numeric_columns:
            self.feature_names.append(column)
            self.feature_names.append(f"{column}__missing")
        for column in self.categorical_columns:
            for category in self.categories[column]:
                self.feature_names.append(f"{column}={category}")
            self.feature_names.append(f"{column}=<other>")

    def transform(self, rows: list[dict]) -> list[list[float]]:
        matrix = []
        for row in rows:
            values = [1.0]
            for column in self.numeric_columns:
                raw = _to_float(row.get(column))
                mean, stdev = self.numeric_stats[column]
                missing = raw is None
                values.append(0.0 if missing else (raw - mean) / stdev)
                values.append(1.0 if missing else 0.0)
            for column in self.categorical_columns:
                value = str(row.get(column) or "<missing>")
                categories = self.categories[column]
                matched = False
                for category in categories:
                    is_match = value == category
                    values.append(1.0 if is_match else 0.0)
                    matched = matched or is_match
                values.append(0.0 if matched else 1.0)
            matrix.append(values)
        return matrix


def _fit_logistic(
    matrix: list[list[float]],
    labels: list[int],
    *,
    epochs: int,
    learning_rate: float,
    l2: float,
) -> list[float]:
    if not matrix:
        return [0.0]
    weights = [0.0 for _ in matrix[0]]
    n_rows = len(matrix)
    for _ in range(max(1, int(epochs))):
        gradients = [0.0 for _ in weights]
        for row, label in zip(matrix, labels):
            predicted = _sigmoid(_dot(weights, row))
            error = predicted - label
            for index, value in enumerate(row):
                gradients[index] += error * value
        for index in range(len(weights)):
            penalty = l2 * weights[index] if index > 0 else 0.0
            weights[index] -= learning_rate * ((gradients[index] / n_rows) + penalty)
    return weights


def _predict_probabilities(matrix: list[list[float]], weights: list[float]) -> list[float]:
    return [_sigmoid(_dot(weights, row)) for row in matrix]


def _classification_metrics(
    y_true: list[int],
    y_pred: list[int],
    probabilities: list[float],
) -> dict:
    if not y_true:
        return {
            "row_count": 0,
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "brier_score": None,
            "confusion_matrix": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
        }
    tp = sum(1 for true, pred in zip(y_true, y_pred) if true == 1 and pred == 1)
    tn = sum(1 for true, pred in zip(y_true, y_pred) if true == 0 and pred == 0)
    fp = sum(1 for true, pred in zip(y_true, y_pred) if true == 0 and pred == 1)
    fn = sum(1 for true, pred in zip(y_true, y_pred) if true == 1 and pred == 0)
    accuracy = (tp + tn) / len(y_true)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall)
        else None
    )
    brier = sum((prob - true) ** 2 for prob, true in zip(probabilities, y_true)) / len(y_true)
    return {
        "row_count": len(y_true),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "brier_score": round(brier, 6),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def _time_split(rows: list[dict], train_ratio: float, validation_ratio: float) -> dict[str, list[dict]]:
    count = len(rows)
    if count <= 2:
        return {"train": rows, "validation": [], "test": []}
    train_end = max(1, min(count - 2, int(count * train_ratio)))
    validation_end = max(train_end + 1, min(count - 1, train_end + int(count * validation_ratio)))
    return {
        "train": rows[:train_end],
        "validation": rows[train_end:validation_end],
        "test": rows[validation_end:],
    }


def _usable_rows(rows: list[dict], target: str) -> list[dict]:
    return [
        row for row in rows
        if _target_value(row.get(target)) is not None
    ]


def _target_value(value) -> int | None:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return 1
    if text in {"0", "false", "no"}:
        return 0
    return None


def _validate_features(features: list[str], target: str) -> None:
    invalid = [
        column for column in features
        if column == target or column in LABEL_LIKE_COLUMNS or _looks_like_label_column(column)
    ]
    if invalid:
        raise ValueError(
            "Feature list includes label/leakage columns: " + ", ".join(sorted(invalid))
        )


def _looks_like_label_column(column: str) -> bool:
    prefixes = (
        "future_",
        "benchmark_future_",
        "excess_return_vs_benchmark_",
    )
    suffixes = (
        "_next_event",
        "_1d",
        "_3d",
        "_7d",
    )
    label_words = (
        "directional_correct",
        "profitable",
        "beat_benchmark",
        "large_loss",
        "high_confidence_wrong",
        "intent_mark_pnl",
        "hold_missed",
    )
    if column.startswith(prefixes):
        return True
    return any(word in column for word in label_words) and column.endswith(suffixes)


def _top_coefficients(weights: list[float], feature_names: list[str], limit: int = 25) -> list[dict]:
    rows = [
        {"feature": name, "coefficient": round(weight, 6)}
        for name, weight in zip(feature_names, weights)
        if name != "bias"
    ]
    rows.sort(key=lambda row: abs(row["coefficient"]), reverse=True)
    return rows[:limit]


def _dot(weights: list[float], row: list[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, row))


def _sigmoid(value: float) -> float:
    if value >= 40:
        return 1.0
    if value <= -40:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def _to_float(value) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp_sort(value) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _string_key_counts(counter: Counter) -> dict:
    return {str(key): value for key, value in sorted(counter.items())}
