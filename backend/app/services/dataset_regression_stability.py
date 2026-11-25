"""Rolling-origin stability analysis for clean downstream regression baselines."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Sequence

import numpy as np
import pandas as pd

from . import dataset_modeling
from .dataset_regression_experiment import _fit

DEFAULT_TRAIN_FRACTIONS = (0.70, 0.80, 0.90)
DEFAULT_TEST_WINDOW_FRACTION = 0.10
MINIMUM_STABILITY_ROWS = 30
MAX_STABILITY_WINDOWS = 10
PREDICTIVE_METRICS = ("mae", "rmse", "r2")


def _frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256(payload).hexdigest()


def _aggregate_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(windows) < 3:
        raise ValueError("at least three completed rolling-origin windows are required")
    result: dict[str, Any] = {"window_count": len(windows), "metrics": {}}
    for name in PREDICTIVE_METRICS:
        values = np.asarray(
            [float(item["metrics"][name]) for item in windows],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError(f"metric {name} contains a non-finite rolling-origin value")
        result["metrics"][name] = {
            "mean": round(float(np.mean(values)), 6),
            "sample_std": round(float(np.std(values, ddof=1)), 6),
            "minimum": round(float(np.min(values)), 6),
            "maximum": round(float(np.max(values)), 6),
            "values_by_window": [round(float(value), 6) for value in values],
        }
    return result


def run_rolling_origin_baseline_stability(
    frame: pd.DataFrame,
    *,
    target_column: str,
    feature_columns: Sequence[str] | None = None,
    numeric_columns: Sequence[str] | None = None,
    categorical_columns: Sequence[str] | None = None,
    train_fractions: Sequence[float] = DEFAULT_TRAIN_FRACTIONS,
    test_window_fraction: float = DEFAULT_TEST_WINDOW_FRACTION,
    alpha: float = 1.0,
) -> dict[str, Any]:
    """Measure clean Ridge baseline variation across expanding temporal windows.

    Each test window is a future interval not used by that fold's training data.
    Later folds expand the training prefix and evaluate on the next non-overlapping
    future interval. All preprocessing is fitted inside the training-only pipeline.
    This measures temporal-window variability, not random-seed variability.
    """
    if not isinstance(frame, pd.DataFrame) or frame.empty or not frame.columns.is_unique:
        raise ValueError("frame must be a non-empty DataFrame with unique columns")
    if not all(isinstance(name, str) and name.strip() for name in frame.columns):
        raise ValueError("frame columns must be non-empty strings")
    if target_column not in frame.columns:
        raise ValueError(f"target column '{target_column}' does not exist")
    if isinstance(alpha, (bool, np.bool_)) or not np.isfinite(alpha) or float(alpha) <= 0:
        raise ValueError("alpha must be a finite number greater than zero")
    if (
        isinstance(test_window_fraction, (bool, np.bool_))
        or not np.isfinite(test_window_fraction)
        or not 0 < float(test_window_fraction) < 0.5
    ):
        raise ValueError("test_window_fraction must be finite and in (0, 0.5)")

    if isinstance(train_fractions, (str, bytes)) or not 3 <= len(train_fractions) <= MAX_STABILITY_WINDOWS:
        raise ValueError("between 3 and 10 train fractions are required")
    fractions: list[float] = []
    for fraction in train_fractions:
        if isinstance(fraction, (bool, np.bool_)) or not np.isfinite(fraction):
            raise ValueError("train fractions must be finite numbers")
        value = float(fraction)
        if not 0.1 < value < 1.0 or value + float(test_window_fraction) > 1.0:
            raise ValueError("each train fraction must leave a complete future test window")
        fractions.append(value)
    if fractions != sorted(fractions) or len(set(fractions)) != len(fractions):
        raise ValueError("train fractions must be distinct and strictly increasing")
    if any(
        right - left < float(test_window_fraction) - 1e-12
        for left, right in zip(fractions, fractions[1:])
    ):
        raise ValueError("rolling-origin future test windows must not overlap")

    normalized = pd.DataFrame(
        {str(name): dataset_modeling._clean_text(frame[name]) for name in frame.columns},
        index=frame.index,
    )
    if normalized.isna().any().any():
        raise ValueError("the clean reference frame must not contain missing or whitespace-only cells")
    if normalized.duplicated().any():
        raise ValueError("the clean reference frame must not contain exact duplicate rows")
    target_values = pd.to_numeric(normalized[target_column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(target_values).all():
        raise ValueError("the regression target must contain only finite numeric values")

    available_features = normalized.drop(columns=[target_column])
    if feature_columns is None:
        selected = tuple(str(name) for name in available_features.columns)
    else:
        if isinstance(feature_columns, (str, bytes)):
            raise ValueError("feature_columns must be a sequence of column names")
        selected = tuple(str(name) for name in feature_columns)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("feature_columns must be non-empty and distinct")
    if target_column in selected:
        raise ValueError("the target column cannot also be a feature")
    unknown = [name for name in selected if name not in available_features.columns]
    if unknown:
        raise ValueError("unknown feature column(s): " + ", ".join(unknown[:10]))

    if (numeric_columns is None) != (categorical_columns is None):
        raise ValueError("numeric_columns and categorical_columns must be supplied together")
    declared_numeric = declared_categorical = None
    if numeric_columns is not None:
        if isinstance(numeric_columns, (str, bytes)) or isinstance(categorical_columns, (str, bytes)):
            raise ValueError("feature type declarations must be sequences")
        declared_numeric = tuple(str(name) for name in numeric_columns)
        declared_categorical = tuple(str(name) for name in categorical_columns)
        declared = declared_numeric + declared_categorical
        if len(set(declared)) != len(declared) or set(declared) != set(selected):
            raise ValueError("numeric and categorical declarations must partition the selected features")

    if len(normalized) < MINIMUM_STABILITY_ROWS:
        raise ValueError(f"at least {MINIMUM_STABILITY_ROWS} clean reference rows are required")

    features = available_features.loc[:, list(selected)].copy(deep=True)
    target = pd.Series(target_values, index=normalized.index, name=target_column)
    reference = pd.concat([features, target], axis=1)
    reference_hash = _frame_sha256(reference)
    snapshot = frame.copy(deep=True)
    per_window: list[dict[str, Any]] = []
    previous_test_end = -1

    for window_index, train_fraction in enumerate(fractions, start=1):
        train_end = int(np.floor(len(features) * train_fraction))
        test_end = int(np.floor(len(features) * (train_fraction + float(test_window_fraction))))
        if train_end < 20 or test_end - train_end < 2:
            raise ValueError("each rolling-origin window needs at least 20 training and 2 test rows")
        if train_end < previous_test_end:
            raise ValueError("rounded rolling-origin future test windows overlap")
        previous_test_end = test_end

        train_x = features.iloc[:train_end].reset_index(drop=True).copy(deep=True)
        test_x = features.iloc[train_end:test_end].reset_index(drop=True).copy(deep=True)
        train_y = target.iloc[:train_end].reset_index(drop=True).copy(deep=True)
        test_y = target.iloc[train_end:test_end].reset_index(drop=True).copy(deep=True)
        if declared_numeric is None:
            numeric = dataset_modeling._infer_numeric_columns(train_x)
            categorical = [str(name) for name in train_x.columns if str(name) not in numeric]
        else:
            numeric = list(declared_numeric)
            categorical = list(declared_categorical)

        test_reference = test_x.copy(deep=True)
        test_reference[target_column] = test_y.to_numpy(copy=True)
        test_hash = _frame_sha256(test_reference)
        test_snapshot = test_reference.copy(deep=True)
        fitted = _fit(
            train_x, test_x, train_y, test_y,
            numeric, categorical, float(alpha),
        )
        pd.testing.assert_frame_equal(test_reference, test_snapshot)
        if _frame_sha256(test_reference) != test_hash:
            raise RuntimeError("a rolling-origin future test window changed during model evaluation")

        per_window.append({
            "window": window_index,
            "train_fraction": train_fraction,
            "test_window_fraction": float(test_window_fraction),
            "split": {
                "strategy": "expanding_window_rolling_origin",
                "train_rows": len(train_x),
                "test_rows": len(test_x),
                "train_positions": [0, train_end - 1],
                "test_positions": [train_end, test_end - 1],
                "clean_test_sha256": test_hash,
                "test_partition_untouched": True,
                "preprocessing_fit_scope": "training_partition_only",
            },
            "features": {
                "selected_columns": list(selected),
                "numeric_columns": numeric,
                "categorical_columns": categorical,
                "type_inference_scope": "current_training_prefix_only",
            },
            "metrics": fitted["metrics"],
        })

    pd.testing.assert_frame_equal(frame, snapshot)
    if _frame_sha256(reference) != reference_hash:
        raise RuntimeError("the clean reference frame changed during rolling-origin evaluation")

    aggregate = _aggregate_windows(per_window)
    return {
        "schema_version": 1,
        "task_type": "regression",
        "evaluation": "clean_baseline_rolling_origin_stability",
        "model": "ridge_regression",
        "target_column": target_column,
        "configuration": {
            "train_fractions": fractions,
            "test_window_fraction": float(test_window_fraction),
            "alpha": float(alpha),
            "feature_columns": list(selected),
            "uncertainty_basis": "sample_standard_deviation_across_non_overlapping_future_windows",
            "random_seed": None,
            "preprocessing_fit_scope": "each_training_prefix_only",
        },
        "clean_reference_frame_sha256": reference_hash,
        "aggregates": aggregate,
        "per_window": per_window,
        "limitations": [
            "This estimates temporal-window variability, not stochastic random-seed variability; Ridge is deterministic for a fixed split and configuration.",
            "Training prefixes expand and therefore overlap between folds; future test windows do not overlap.",
            "The sample standard deviation across three windows is descriptive and is not a confidence interval.",
            "One UCI Bike Sharing reference and one fixed Ridge alpha are evaluated; no model tuning is performed.",
            "All preprocessing and feature-type inference are fitted or derived from each training prefix only.",
        ],
    }
