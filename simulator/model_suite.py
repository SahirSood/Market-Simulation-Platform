"""Multi-model research suite for replay ML datasets.

This module is for analysis, not live trading. It trains several leakage-safe
tabular classifiers on exported replay rows and writes a compact JSON report.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from baseline_model import DEFAULT_FEATURE_COLUMNS, LABEL_LIKE_COLUMNS


DEFAULT_TARGETS = [
    "directional_correct_1d",
    "beat_benchmark_1d",
    "directional_correct_3d",
    "beat_benchmark_3d",
    "large_loss_1d",
    "high_confidence_wrong_1d",
]


def train_model_suite_from_csv(
    *,
    dataset_path: str | Path,
    report_path: str | Path | None = None,
    targets: Iterable[str] | None = None,
    feature_columns: Iterable[str] | None = None,
    time_column: str = "as_of_time",
    min_rows: int = 50,
    random_state: int = 42,
) -> dict:
    """Train several tabular classifiers for each requested target."""
    pd, np, sklearn = _load_ml_dependencies()
    df = pd.read_csv(dataset_path)
    features = [
        column for column in (feature_columns or DEFAULT_FEATURE_COLUMNS)
        if column in df.columns and column not in LABEL_LIKE_COLUMNS
    ]
    targets = [target for target in (targets or DEFAULT_TARGETS) if target in df.columns]

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset": str(dataset_path),
        "row_count": int(len(df)),
        "feature_columns": features,
        "targets": {},
        "model_names": [
            "logistic_regression",
            "random_forest",
            "extra_trees",
            "gradient_boosting",
            "dummy_majority",
        ],
    }
    for target in targets:
        report["targets"][target] = _train_target_suite(
            df,
            target=target,
            feature_columns=features,
            time_column=time_column,
            min_rows=min_rows,
            random_state=random_state,
            pd=pd,
            np=np,
            sklearn=sklearn,
        )

    if report_path:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def _train_target_suite(
    df,
    *,
    target: str,
    feature_columns: list[str],
    time_column: str,
    min_rows: int,
    random_state: int,
    pd,
    np,
    sklearn,
) -> dict:
    usable = df[df[target].astype(str).isin(["0", "1", "0.0", "1.0"])].copy()
    usable[target] = usable[target].astype(float).astype(int)
    if time_column in usable.columns:
        usable = usable.sort_values(time_column)

    label_counts = {
        str(key): int(value)
        for key, value in usable[target].value_counts().sort_index().items()
    }
    result = {
        "status": "ok",
        "usable_rows": int(len(usable)),
        "label_counts": label_counts,
        "warnings": [],
        "models": {},
        "best_model_by_test_f1": None,
        "best_model_by_test_accuracy": None,
    }
    if len(usable) < min_rows:
        result["warnings"].append(
            f"Only {len(usable)} usable rows; treat this target as exploratory."
        )
    if len(label_counts) < 2:
        result["status"] = "insufficient_label_diversity"
        result["warnings"].append("Target has only one class.")
        return result

    train_df, validation_df, test_df = _time_split_df(usable, pd=pd)
    result["split"] = {
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(validation_df)),
        "test_rows": int(len(test_df)),
        "method": "time_ordered",
    }
    if len(test_df) == 0:
        result["status"] = "insufficient_test_rows"
        result["warnings"].append("No test rows after time split.")
        return result

    x_train = train_df[feature_columns]
    y_train = train_df[target]
    parts = {
        "train": (x_train, y_train),
        "validation": (validation_df[feature_columns], validation_df[target]),
        "test": (test_df[feature_columns], test_df[target]),
    }
    numeric_features, categorical_features = _feature_types(train_df, feature_columns, pd=pd)
    preprocessor = _preprocessor(
        numeric_features,
        categorical_features,
        sklearn=sklearn,
    )
    models = _models(random_state=random_state, sklearn=sklearn)
    feature_names = None
    for name, model in models.items():
        pipeline = sklearn.pipeline.Pipeline([
            ("preprocess", preprocessor),
            ("model", model),
        ])
        pipeline.fit(x_train, y_train)
        if feature_names is None:
            feature_names = _processed_feature_names(
                pipeline.named_steps["preprocess"],
                numeric_features,
                categorical_features,
            )
        result["models"][name] = _evaluate_pipeline(
            pipeline,
            parts,
            feature_names=feature_names,
            sklearn=sklearn,
            np=np,
        )

    result["best_model_by_test_f1"] = _best_model(result["models"], metric="f1")
    result["best_model_by_test_accuracy"] = _best_model(result["models"], metric="accuracy")
    result["calibration"] = _confidence_calibration(usable, target)
    return result


def _load_ml_dependencies():
    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
        import sklearn  # type: ignore
        import sklearn.compose  # type: ignore
        import sklearn.dummy  # type: ignore
        import sklearn.ensemble  # type: ignore
        import sklearn.impute  # type: ignore
        import sklearn.linear_model  # type: ignore
        import sklearn.metrics  # type: ignore
        import sklearn.pipeline  # type: ignore
        import sklearn.preprocessing  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only in missing envs
        raise RuntimeError(
            "The model suite requires pandas, numpy, and scikit-learn. "
            "Install project requirements before running it."
        ) from exc
    return pd, np, sklearn


def _models(*, random_state: int, sklearn) -> dict:
    return {
        "logistic_regression": sklearn.linear_model.LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=random_state,
        ),
        "random_forest": sklearn.ensemble.RandomForestClassifier(
            n_estimators=300,
            max_depth=6,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=random_state,
        ),
        "extra_trees": sklearn.ensemble.ExtraTreesClassifier(
            n_estimators=300,
            max_depth=6,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=random_state,
        ),
        "gradient_boosting": sklearn.ensemble.GradientBoostingClassifier(
            n_estimators=120,
            learning_rate=0.05,
            max_depth=2,
            random_state=random_state,
        ),
        "dummy_majority": sklearn.dummy.DummyClassifier(strategy="most_frequent"),
    }


def _preprocessor(numeric_features: list[str], categorical_features: list[str], *, sklearn):
    try:
        encoder = sklearn.preprocessing.OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # older sklearn
        encoder = sklearn.preprocessing.OneHotEncoder(handle_unknown="ignore", sparse=False)
    return sklearn.compose.ColumnTransformer(
        transformers=[
            (
                "num",
                sklearn.pipeline.Pipeline([
                    ("impute", sklearn.impute.SimpleImputer(strategy="median")),
                    ("scale", sklearn.preprocessing.StandardScaler()),
                ]),
                numeric_features,
            ),
            (
                "cat",
                sklearn.pipeline.Pipeline([
                    ("impute", sklearn.impute.SimpleImputer(strategy="most_frequent")),
                    ("onehot", encoder),
                ]),
                categorical_features,
            ),
        ],
        remainder="drop",
    )


def _feature_types(df, feature_columns: list[str], *, pd) -> tuple[list[str], list[str]]:
    numeric = []
    categorical = []
    for column in feature_columns:
        series = pd.to_numeric(df[column], errors="coerce")
        non_empty = df[column].notna() & (df[column].astype(str).str.strip() != "")
        numeric_ratio = float(series[non_empty].notna().mean()) if non_empty.any() else 0.0
        if numeric_ratio >= 0.95:
            numeric.append(column)
        else:
            categorical.append(column)
    return numeric, categorical


def _time_split_df(df, *, pd):
    count = len(df)
    train_end = max(1, min(count - 2, int(count * 0.7)))
    validation_end = max(train_end + 1, min(count - 1, train_end + int(count * 0.15)))
    return (
        df.iloc[:train_end].copy(),
        df.iloc[train_end:validation_end].copy(),
        df.iloc[validation_end:].copy(),
    )


def _evaluate_pipeline(pipeline, parts: dict, *, feature_names: list[str], sklearn, np) -> dict:
    output = {"metrics": {}, "top_features": []}
    for split_name, (x_part, y_part) in parts.items():
        if len(y_part) == 0:
            output["metrics"][split_name] = _empty_metrics()
            continue
        pred = pipeline.predict(x_part)
        if hasattr(pipeline, "predict_proba"):
            prob = pipeline.predict_proba(x_part)[:, 1]
        else:
            prob = pred.astype(float)
        output["metrics"][split_name] = _metrics(y_part, pred, prob, sklearn=sklearn)
    output["top_features"] = _top_model_features(
        pipeline.named_steps["model"],
        feature_names,
        np=np,
    )
    return output


def _metrics(y_true, y_pred, prob, *, sklearn) -> dict:
    labels = [0, 1]
    try:
        roc_auc = sklearn.metrics.roc_auc_score(y_true, prob) if len(set(y_true)) > 1 else None
    except ValueError:
        roc_auc = None
    return {
        "row_count": int(len(y_true)),
        "accuracy": _round(sklearn.metrics.accuracy_score(y_true, y_pred)),
        "precision": _round(sklearn.metrics.precision_score(y_true, y_pred, zero_division=0)),
        "recall": _round(sklearn.metrics.recall_score(y_true, y_pred, zero_division=0)),
        "f1": _round(sklearn.metrics.f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": _round(roc_auc),
        "brier_score": _round(sklearn.metrics.brier_score_loss(y_true, prob), 6),
        "confusion_matrix": _confusion_dict(
            sklearn.metrics.confusion_matrix(y_true, y_pred, labels=labels)
        ),
    }


def _empty_metrics() -> dict:
    return {
        "row_count": 0,
        "accuracy": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "roc_auc": None,
        "brier_score": None,
        "confusion_matrix": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
    }


def _confusion_dict(matrix) -> dict:
    tn, fp, fn, tp = matrix.ravel()
    return {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)}


def _top_model_features(model, feature_names: list[str], *, np, limit: int = 20) -> list[dict]:
    values = None
    if hasattr(model, "feature_importances_"):
        values = model.feature_importances_
    elif hasattr(model, "coef_"):
        values = np.ravel(model.coef_)
    if values is None:
        return []
    rows = [
        {"feature": name, "importance": _round(float(value), 6)}
        for name, value in zip(feature_names, values)
    ]
    rows.sort(key=lambda row: abs(row["importance"]), reverse=True)
    return rows[:limit]


def _processed_feature_names(preprocessor, numeric_features: list[str], categorical_features: list[str]) -> list[str]:
    names = []
    names.extend(numeric_features)
    if categorical_features:
        cat_pipe = preprocessor.named_transformers_["cat"]
        encoder = cat_pipe.named_steps["onehot"]
        names.extend(list(encoder.get_feature_names_out(categorical_features)))
    return names


def _best_model(models: dict, *, metric: str) -> str | None:
    scored = []
    for name, result in models.items():
        value = ((result.get("metrics") or {}).get("test") or {}).get(metric)
        if value is not None:
            scored.append((name, value))
    if not scored:
        return None
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[0][0]


def _confidence_calibration(df, target: str) -> list[dict]:
    if "confidence" not in df.columns:
        return []
    rows = []
    conf = df["confidence"].apply(lambda value: float(value) if str(value).strip() else float("nan"))
    for label, low, high in (
        ("low", 0.0, 0.4),
        ("medium", 0.4, 0.7),
        ("high", 0.7, 1.01),
    ):
        bucket = df[(conf >= low) & (conf < high)]
        if len(bucket) == 0:
            continue
        rows.append({
            "bucket": label,
            "row_count": int(len(bucket)),
            "avg_confidence": _round(conf.loc[bucket.index].mean(), 4),
            "actual_positive_rate": _round(bucket[target].astype(int).mean(), 4),
        })
    return rows


def _round(value, digits: int = 4):
    if value is None:
        return None
    return round(float(value), digits)
