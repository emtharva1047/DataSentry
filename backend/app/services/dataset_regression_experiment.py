"""Leakage-safe downstream regression experiments with training-only corruption."""
from __future__ import annotations
import json
from hashlib import sha256
from time import perf_counter
from typing import Any, Sequence
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from . import dataset_cleaning, dataset_modeling
from .dataset_research import aggregate_seed_metrics, inject_synthetic_corruption

DEFAULT_REGRESSION_SEEDS = (42, 123, 2026)
MINIMUM_REGRESSION_ROWS = 30
MAX_REGRESSION_SEEDS = 10


def _frame_sha256(frame: pd.DataFrame) -> str:
    return sha256(frame.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def _validate(
    frame: pd.DataFrame, target_column: str, feature_columns: Sequence[str] | None,
    numeric_columns: Sequence[str] | None, categorical_columns: Sequence[str] | None,
    seeds: Sequence[int], test_size: float, corruption_rate: float,
):
    if not isinstance(frame, pd.DataFrame) or frame.empty or not frame.columns.is_unique:
        raise ValueError("frame must be a non-empty DataFrame with unique columns")
    if not all(isinstance(name, str) and name.strip() for name in frame.columns):
        raise ValueError("frame columns must be non-empty strings")
    if target_column not in frame.columns:
        raise ValueError(f"target column '{target_column}' does not exist")
    if isinstance(test_size, (bool, np.bool_)) or not np.isfinite(test_size) or not 0.1 < float(test_size) < 0.5:
        raise ValueError("test_size must be greater than 0.1 and less than 0.5")
    if isinstance(corruption_rate, (bool, np.bool_)) or not np.isfinite(corruption_rate) or not 0 < float(corruption_rate) <= 0.5:
        raise ValueError("corruption_rate must be in (0, 0.5]")
    if isinstance(seeds, (str, bytes)) or len(seeds) < 3 or len(seeds) > MAX_REGRESSION_SEEDS:
        raise ValueError("between 3 and 10 distinct seeds are required")
    seed_values = []
    for seed in seeds:
        if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)) or not 0 <= int(seed) <= 2**32 - 1:
            raise ValueError("seeds must be unsigned 32-bit integers")
        seed_values.append(int(seed))
    if len(set(seed_values)) != len(seed_values):
        raise ValueError("seeds must be distinct")

    normalized = pd.DataFrame(
        {str(name): dataset_modeling._clean_text(frame[name]) for name in frame.columns},
        index=frame.index,
    )
    if normalized.isna().any().any():
        raise ValueError("the clean reference frame must not contain missing or whitespace-only cells")
    if normalized.duplicated().any():
        raise ValueError("the clean reference frame must not contain exact duplicate rows")
    raw_target = pd.to_numeric(normalized[target_column], errors="coerce")
    target_values = raw_target.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(target_values).all():
        raise ValueError("the regression target must contain only finite numeric values")

    all_features = normalized.drop(columns=[target_column])
    if feature_columns is None:
        selected = tuple(str(name) for name in all_features.columns)
    else:
        if isinstance(feature_columns, (str, bytes)):
            raise ValueError("feature_columns must be a sequence of column names")
        selected = tuple(str(name) for name in feature_columns)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("feature_columns must be non-empty and distinct")
    if target_column in selected:
        raise ValueError("the target column cannot also be a feature")
    unknown = [name for name in selected if name not in all_features.columns]
    if unknown:
        raise ValueError("unknown feature column(s): " + ", ".join(unknown[:10]))

    if (numeric_columns is None) != (categorical_columns is None):
        raise ValueError("numeric_columns and categorical_columns must be supplied together")
    explicit_numeric = explicit_categorical = None
    if numeric_columns is not None:
        if isinstance(numeric_columns, (str, bytes)) or isinstance(categorical_columns, (str, bytes)):
            raise ValueError("feature type declarations must be sequences")
        explicit_numeric = tuple(str(name) for name in numeric_columns)
        explicit_categorical = tuple(str(name) for name in categorical_columns)
        declared = explicit_numeric + explicit_categorical
        if len(set(declared)) != len(declared) or set(declared) != set(selected):
            raise ValueError("numeric and categorical declarations must partition the selected features")
    if len(normalized) < MINIMUM_REGRESSION_ROWS:
        raise ValueError(f"at least {MINIMUM_REGRESSION_ROWS} clean reference rows are required")
    features = all_features.loc[:, list(selected)].copy(deep=True)
    target = pd.Series(target_values, index=normalized.index, name=target_column)
    return features, target, selected, tuple(seed_values), explicit_numeric, explicit_categorical


def _fit(
    train_x: pd.DataFrame, test_x: pd.DataFrame, train_y: pd.Series, test_y: pd.Series,
    numeric: list[str], categorical: list[str], alpha: float,
) -> dict[str, Any]:
    train = dataset_modeling._prepare_partition(train_x, numeric, categorical)
    test = dataset_modeling._prepare_partition(test_x, numeric, categorical)
    pipeline = Pipeline([
        ("preprocessor", dataset_modeling._build_preprocessor(numeric, categorical)),
        ("model", Ridge(alpha=alpha)),
    ])
    started = perf_counter()
    pipeline.fit(train, train_y)
    prediction = pipeline.predict(test)
    elapsed = perf_counter() - started
    return {"metrics": {
        "mae": round(float(mean_absolute_error(test_y, prediction)), 6),
        "rmse": round(float(np.sqrt(mean_squared_error(test_y, prediction))), 6),
        "r2": round(float(r2_score(test_y, prediction)), 6),
        "runtime_seconds": round(float(elapsed), 6),
    }}


def run_regression_corruption_experiment(
    frame: pd.DataFrame, *, target_column: str,
    feature_columns: Sequence[str] | None = None,
    numeric_columns: Sequence[str] | None = None,
    categorical_columns: Sequence[str] | None = None,
    seeds: Sequence[int] = DEFAULT_REGRESSION_SEEDS,
    test_size: float = 0.25, corruption_rate: float = 0.05, alpha: float = 1.0,
) -> dict[str, Any]:
    """Compare clean, missing-corrupted, and production-cleaned training on a future holdout.

    Input rows must already be chronologically ordered. The first partition is
    training; the final partition is never passed to corruption or cleaning.
    """
    if isinstance(alpha, (bool, np.bool_)) or not np.isfinite(alpha) or float(alpha) <= 0:
        raise ValueError("alpha must be a finite number greater than zero")
    snapshot = frame.copy(deep=True)
    features, target, selected, seed_values, declared_numeric, declared_categorical = _validate(
        frame, target_column, feature_columns, numeric_columns, categorical_columns,
        seeds, test_size, corruption_rate,
    )
    split = int(np.floor(len(features) * (1.0 - float(test_size))))
    if split < 20 or len(features) - split < 2:
        raise ValueError("the chronological split needs at least 20 training and 2 test rows")

    per_seed = []
    condition_names = ("clean", "corrupted", "cleaned_corrupted")
    for seed in seed_values:
        train_x = features.iloc[:split].reset_index(drop=True).copy(deep=True)
        test_x = features.iloc[split:].reset_index(drop=True).copy(deep=True)
        train_y = target.iloc[:split].reset_index(drop=True).copy(deep=True)
        test_y = target.iloc[split:].reset_index(drop=True).copy(deep=True)
        if declared_numeric is None:
            numeric = dataset_modeling._infer_numeric_columns(train_x)
            categorical = [str(name) for name in train_x.columns if str(name) not in numeric]
        else:
            numeric = list(declared_numeric)
            categorical = list(declared_categorical)

        corruption_seed = (seed + 130363) % (2**32)
        corruption = inject_synthetic_corruption(
            train_x, rate=float(corruption_rate), seed=corruption_seed, defects=["missingness"]
        )
        defect = corruption.ground_truth["defects"]["missingness"]
        if defect["status"] != "completed":
            raise ValueError("training missingness could not be injected: " + str(defect.get("skipped_reason")))
        cleaned, cleaning = dataset_cleaning._transform(corruption.frame, {
            "drop_exact_duplicates": False,
            "fill_numeric_median": numeric,
            "fill_categorical_mode": categorical,
            "trim_whitespace": [],
            "lowercase_categories": [],
        })

        test_reference = test_x.copy(deep=True)
        test_reference[target_column] = test_y
        test_hash = _frame_sha256(test_reference)
        test_snapshot = test_reference.copy(deep=True)
        train_conditions = {"clean": train_x, "corrupted": corruption.frame, "cleaned_corrupted": cleaned}
        conditions = {
            name: _fit(train_conditions[name], test_x, train_y, test_y, numeric, categorical, float(alpha))
            for name in condition_names
        }
        pd.testing.assert_frame_equal(test_reference, test_snapshot)
        if _frame_sha256(test_reference) != test_hash:
            raise RuntimeError("the clean future test partition changed during the experiment")

        labels = corruption.ground_truth["cell_labels"]
        label_bytes = json.dumps(labels, sort_keys=True, separators=(",", ":")).encode("utf-8")
        by_column: dict[str, int] = {}
        for label in labels:
            by_column[label["column"]] = by_column.get(label["column"], 0) + 1
        per_seed.append({
            "seed": seed,
            "corruption_seed": corruption_seed,
            "split": {
                "strategy": "chronological_ordered_holdout",
                "test_size": float(test_size),
                "train_rows": len(train_x),
                "test_rows": len(test_x),
                "train_positions": [0, split - 1],
                "test_positions": [split, len(features) - 1],
                "clean_test_sha256": test_hash,
                "test_partition_untouched": True,
            },
            "features": {
                "selected_columns": list(selected),
                "numeric_columns": numeric,
                "categorical_columns": categorical,
                "type_inference_scope": "clean_training_partition_only",
            },
            "corruption": {
                "defect_type": "missingness",
                "rate": float(corruption_rate),
                "injected_cells": int(defect["injected_count"]),
                "per_column_counts": by_column,
                "ground_truth_sha256": sha256(label_bytes).hexdigest(),
            },
            "cleaning": {
                "changed": bool(cleaning["changed"]),
                "changed_row_count": int(cleaning["preview"]["changed_row_count"]),
                "operations": cleaning["preview"]["operations"],
            },
            "conditions": conditions,
        })

    pd.testing.assert_frame_equal(frame, snapshot)
    aggregates = {
        name: aggregate_seed_metrics([
            {"seed": run["seed"], "metrics": run["conditions"][name]["metrics"]}
            for run in per_seed
        ])
        for name in condition_names
    }
    paired = aggregate_seed_metrics([
        {
            "seed": run["seed"],
            "metrics": {
                metric: run["conditions"]["cleaned_corrupted"]["metrics"][metric]
                - run["conditions"]["corrupted"]["metrics"][metric]
                for metric in ("mae", "rmse", "r2")
            },
        }
        for run in per_seed
    ])
    reference = pd.concat([features, target.rename(target_column)], axis=1)
    return {
        "schema_version": 1,
        "task_type": "regression",
        "model": "ridge_regression",
        "target_column": target_column,
        "configuration": {
            "seeds": list(seed_values),
            "test_size": float(test_size),
            "split_strategy": "chronological_ordered_holdout",
            "corruption_type": "missingness",
            "corruption_rate": float(corruption_rate),
            "ridge_alpha": float(alpha),
            "feature_columns": list(selected),
            "preprocessing_fit_scope": "each_training_condition_only",
        },
        "clean_reference_frame_sha256": _frame_sha256(reference),
        "aggregates": aggregates,
        "paired_cleaned_minus_corrupted": paired,
        "per_seed": per_seed,
        "limitations": [
            "The input frame must be chronologically ordered.",
            "Seeds vary training corruption; the temporal split is fixed.",
            "Only training features receive missingness; target and future test rows remain untouched.",
            "Median/mode imputation is one explicit policy, not a universal correction.",
            "Ridge uses a fixed alpha and one chronological holdout; no rolling-origin validation is performed.",
        ],
    }
