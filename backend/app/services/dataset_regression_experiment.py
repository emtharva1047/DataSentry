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
SUPPORTED_REGRESSION_CORRUPTIONS = ("missingness", "duplicates", "invalid_values", "numerical_anomalies")


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
    corruption_type: str = "missingness",
) -> dict[str, Any]:
    """Compare clean, corrupted, and production-cleaned training on a future holdout.

    Missingness and invalid-value tokens are injected into training features.
    Duplicate corruption appends exact copies of complete training rows,
    including their target, so feature/label alignment is preserved. The
    chronological future test partition is never passed to corruption or cleaning.
    """
    if isinstance(alpha, (bool, np.bool_)) or not np.isfinite(alpha) or float(alpha) <= 0:
        raise ValueError("alpha must be a finite number greater than zero")
    if not isinstance(corruption_type, str) or corruption_type not in SUPPORTED_REGRESSION_CORRUPTIONS:
        raise ValueError(
            "corruption_type must be one of: " + ", ".join(SUPPORTED_REGRESSION_CORRUPTIONS)
        )
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
        if corruption_type == "duplicates":
            # Include the target so every appended feature row retains its true label.
            corruption_input = train_x.copy(deep=True)
            corruption_input[target_column] = train_y.to_numpy(copy=True)
        else:
            corruption_input = train_x.copy(deep=True)

        corruption = inject_synthetic_corruption(
            corruption_input,
            rate=float(corruption_rate),
            seed=corruption_seed,
            defects=[corruption_type],
            numeric_columns=numeric,
        )
        defect = corruption.ground_truth["defects"][corruption_type]
        if defect["status"] != "completed":
            raise ValueError(
                f"training {corruption_type} could not be injected: "
                + str(defect.get("skipped_reason"))
            )

        if corruption_type in {"missingness", "invalid_values", "numerical_anomalies"}:
            corrupted_x = corruption.frame.copy(deep=True)
            corrupted_y = train_y.copy(deep=True)
            cleaned_x, cleaning = dataset_cleaning._transform(corrupted_x, {
                "drop_exact_duplicates": False,
                "fill_numeric_median": numeric if corruption_type in {"missingness", "invalid_values"} else [],
                "fill_categorical_mode": categorical if corruption_type == "missingness" else [],
                "trim_whitespace": [],
                "lowercase_categories": [],
                "clip_numeric_iqr": numeric if corruption_type == "numerical_anomalies" else [],
            })
            cleaned_y = train_y.copy(deep=True)
            injection_unit = "eligible_feature_cells"
            injected_count = int(defect["injected_count"])
            injection_records = defect["records"]
            label_payload = {
                "defect": defect,
                "cell_labels": corruption.ground_truth["cell_labels"],
            }
            per_column_counts: dict[str, int] = {}
            for record in injection_records:
                column = str(record["column"])
                per_column_counts[column] = per_column_counts.get(column, 0) + 1
            if corruption_type == "invalid_values":
                for column in numeric:
                    values = pd.to_numeric(cleaned_x[column], errors="coerce").to_numpy(dtype=float)
                    if not np.isfinite(values).all():
                        raise RuntimeError(
                            f"production median cleaning left invalid numeric values in '{column}'"
                        )
            if corruption_type == "numerical_anomalies":
                clip_operations = {
                    item["columns"][0]: item
                    for item in cleaning["preview"]["operations"]
                    if item["operation"] == "clip_numeric_iqr"
                }
                for record in injection_records:
                    column = str(record["column"])
                    operation = clip_operations.get(column)
                    if operation is None:
                        raise RuntimeError(f"production IQR cleaning omitted injected column '{column}'")
                    cleaned_value = float(cleaned_x.iloc[int(record["row_index"])][column])
                    if cleaned_value > float(operation["upper_fence"]) or cleaned_value < float(operation["lower_fence"]):
                        raise RuntimeError(f"production IQR cleaning left an injected anomaly in '{column}'")
        else:
            corrupted_full = corruption.frame.copy(deep=True)
            corrupted_y = pd.to_numeric(
                corrupted_full.pop(target_column), errors="raise"
            ).astype(float)
            corrupted_x = corrupted_full
            cleaned_full, cleaning = dataset_cleaning._transform(corruption.frame, {
                "drop_exact_duplicates": True,
                "fill_numeric_median": [],
                "fill_categorical_mode": [],
                "trim_whitespace": [],
                "lowercase_categories": [],
            })
            cleaned_y = pd.to_numeric(
                cleaned_full.pop(target_column), errors="raise"
            ).astype(float)
            cleaned_x = cleaned_full
            # Exact duplicate removal must restore the original aligned training
            # feature/target pairs, not merely the original feature row count.
            pd.testing.assert_frame_equal(
                cleaned_x.reset_index(drop=True), train_x.reset_index(drop=True),
                check_dtype=False,
            )
            pd.testing.assert_series_equal(
                cleaned_y.reset_index(drop=True), train_y.reset_index(drop=True),
                check_names=False,
            )
            injection_unit = "source_training_rows"
            injected_count = int(defect["injected_count"])
            injection_records = corruption.ground_truth["duplicate_rows"]
            label_payload = {
                "defect": defect,
                "duplicate_rows": corruption.ground_truth["duplicate_rows"],
            }
            per_column_counts = {}

        test_reference = test_x.copy(deep=True)
        test_reference[target_column] = test_y
        test_hash = _frame_sha256(test_reference)
        test_snapshot = test_reference.copy(deep=True)
        train_conditions = {
            "clean": (train_x, train_y),
            "corrupted": (corrupted_x, corrupted_y),
            "cleaned_corrupted": (cleaned_x, cleaned_y),
        }
        conditions = {
            name: _fit(
                train_conditions[name][0], test_x,
                train_conditions[name][1], test_y,
                numeric, categorical, float(alpha),
            )
            for name in condition_names
        }
        pd.testing.assert_frame_equal(test_reference, test_snapshot)
        if _frame_sha256(test_reference) != test_hash:
            raise RuntimeError("the clean future test partition changed during the experiment")

        label_bytes = json.dumps(
            label_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
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
                "defect_type": corruption_type,
                "rate": float(corruption_rate),
                "injection_unit": injection_unit,
                "injected_count": injected_count,
                "injected_cells": injected_count if corruption_type in {"missingness", "invalid_values", "numerical_anomalies"} else None,
                "injected_rows": injected_count if corruption_type == "duplicates" else None,
                "corrupted_training_rows": len(corrupted_x),
                "cleaned_training_rows": len(cleaned_x),
                "per_column_counts": per_column_counts,
                "ground_truth_records": injection_records,
                "ground_truth_sha256": sha256(label_bytes).hexdigest(),
            },
            "cleaning": {
                "changed": bool(cleaning["changed"]),
                "changed_row_count": int(cleaning["preview"]["changed_row_count"]),
                "removed_row_count": int(cleaning["preview"]["removed_row_count"]),
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
        "schema_version": 4,
        "task_type": "regression",
        "model": "ridge_regression",
        "target_column": target_column,
        "configuration": {
            "seeds": list(seed_values),
            "test_size": float(test_size),
            "split_strategy": "chronological_ordered_holdout",
            "corruption_type": corruption_type,
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
            "Only the selected training defect is injected; future test rows and targets remain untouched.",
            "Duplicate corruption appends exact feature/target pairs and production cleaning removes exact duplicate rows.",
            "Median/mode imputation is one explicit missingness policy, not a universal correction.",
            "For invalid_values, the selected numeric-median cleaning operation explicitly coerces non-numeric and non-finite cells to missing before imputation; cells are counted separately in cleaning evidence.",
            "For numerical_anomalies, the production clip_numeric_iqr operation fits Tukey 1.5xIQR fences on the corrupted training partition only and clips both tails; it can also clip legitimate training extremes.",
            "Ridge uses a fixed alpha and one chronological holdout; no rolling-origin validation is performed.",
        ],
    }
