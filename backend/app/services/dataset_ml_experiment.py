"""Downstream classification experiments with corruption restricted to training rows."""
from __future__ import annotations

from hashlib import sha256
from time import perf_counter
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from . import dataset_cleaning, dataset_modeling
from .dataset_research import aggregate_seed_metrics, inject_synthetic_corruption

DEFAULT_EXPERIMENT_SEEDS = (42, 123, 2026)
MAX_EXPERIMENT_SEEDS = 10
MINIMUM_ROWS = 30


def _frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256(payload).hexdigest()


def _validate_experiment(
    frame: pd.DataFrame,
    target_column: str,
    seeds: Sequence[int],
    test_size: float,
    corruption_rate: float,
) -> tuple[pd.DataFrame, pd.Series, tuple[int, ...]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("frame must be a non-empty pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("frame must have unique column names")
    if not all(isinstance(name, str) and name.strip() for name in frame.columns):
        raise ValueError("frame columns must be non-empty strings")
    if target_column not in frame.columns:
        raise ValueError(f"target column '{target_column}' does not exist")
    if not np.isfinite(test_size) or not 0.1 < float(test_size) < 0.5:
        raise ValueError("test_size must be greater than 0.1 and less than 0.5")
    if not np.isfinite(corruption_rate) or not 0 < float(corruption_rate) <= 0.5:
        raise ValueError("corruption_rate must be in (0, 0.5]")
    if len(seeds) < 3 or len(seeds) > MAX_EXPERIMENT_SEEDS:
        raise ValueError("between 3 and 10 distinct seeds are required")

    normalized_seeds: list[int] = []
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
            raise ValueError("seeds must be unsigned 32-bit integers")
        value = int(seed)
        if not 0 <= value <= 2**32 - 1:
            raise ValueError("seeds must be unsigned 32-bit integers")
        normalized_seeds.append(value)
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must be distinct")

    normalized = pd.DataFrame(
        {
            name: dataset_modeling._clean_text(frame[name])
            for name in frame.columns
        },
        index=frame.index,
    )
    if normalized.isna().any().any():
        raise ValueError("the clean reference frame must not contain missing or whitespace-only cells")
    if normalized.duplicated().any():
        raise ValueError("the clean reference frame must not contain exact duplicate rows")

    target = normalized[target_column].astype(str)
    class_counts = target.value_counts()
    if len(class_counts) < 2:
        raise ValueError("classification requires at least two target classes")
    if int(class_counts.min()) < 2:
        raise ValueError("every target class needs at least two rows")
    row_count = len(normalized)
    expected_test_rows = int(np.ceil(row_count * float(test_size)))
    if row_count < MINIMUM_ROWS or expected_test_rows < len(class_counts):
        raise ValueError("the reference dataset is too small for the requested stratified holdout")

    features = normalized.drop(columns=[target_column])
    if features.shape[1] == 0:
        raise ValueError("at least one feature column is required")
    return features, target, tuple(normalized_seeds)


def _fit_condition(
    training_features: pd.DataFrame,
    test_features: pd.DataFrame,
    training_target: pd.Series,
    test_target: pd.Series,
    numeric_columns: list[str],
    categorical_columns: list[str],
    random_state: int,
) -> dict[str, Any]:
    """Fit the production baseline model/preprocessor on one training condition."""
    prepared_train = dataset_modeling._prepare_partition(
        training_features, numeric_columns, categorical_columns
    )
    prepared_test = dataset_modeling._prepare_partition(
        test_features, numeric_columns, categorical_columns
    )
    pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                dataset_modeling._build_preprocessor(
                    numeric_columns, categorical_columns
                ),
            ),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=random_state,
                ),
            ),
        ]
    )

    started = perf_counter()
    pipeline.fit(prepared_train, training_target)
    predictions = pipeline.predict(prepared_test)
    elapsed = perf_counter() - started

    labels = sorted(training_target.unique().tolist())
    matrix = confusion_matrix(test_target, predictions, labels=labels)
    metrics = {
        "accuracy": round(float(accuracy_score(test_target, predictions)), 6),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(test_target, predictions)), 6
        ),
        "macro_precision": round(
            float(
                precision_score(
                    test_target, predictions, average="macro", zero_division=0
                )
            ),
            6,
        ),
        "macro_recall": round(
            float(
                recall_score(
                    test_target, predictions, average="macro", zero_division=0
                )
            ),
            6,
        ),
        "macro_f1": round(
            float(f1_score(test_target, predictions, average="macro", zero_division=0)),
            6,
        ),
        "runtime_seconds": round(float(elapsed), 6),
    }
    return {
        "metrics": metrics,
        "confusion_matrix": {
            "labels": labels,
            "counts": matrix.astype(int).tolist(),
        },
    }


def run_classification_corruption_experiment(
    frame: pd.DataFrame,
    *,
    target_column: str,
    seeds: Sequence[int] = DEFAULT_EXPERIMENT_SEEDS,
    test_size: float = 0.25,
    corruption_rate: float = 0.05,
) -> dict[str, Any]:
    """Compare clean, corrupted, and cleaned-corrupted training on the same clean test split.

    A stratified split is made from the untouched reference data first. Only the
    training feature partition is corrupted. The test partition is never passed
    to corruption or cleaning and is reused unchanged for all three conditions
    within a seed. Feature types are inferred from clean training rows only.
    """
    source = frame.copy(deep=True)
    features, target, normalized_seeds = _validate_experiment(
        frame, target_column, seeds, test_size, corruption_rate
    )
    per_seed: list[dict[str, Any]] = []
    condition_names = ("clean", "corrupted", "cleaned_corrupted")

    for seed in normalized_seeds:
        X_train, X_test, y_train, y_test = train_test_split(
            features,
            target,
            test_size=float(test_size),
            random_state=seed,
            stratify=target,
        )
        X_train = X_train.reset_index(drop=True)
        X_test = X_test.reset_index(drop=True)
        y_train = y_train.reset_index(drop=True)
        y_test = y_test.reset_index(drop=True)

        # Type inference is based on the clean training partition, never the test set.
        numeric_columns = dataset_modeling._infer_numeric_columns(X_train)
        categorical_columns = [
            str(name) for name in X_train.columns if str(name) not in numeric_columns
        ]
        if not categorical_columns:
            raise ValueError(
                "categorical_inconsistency evaluation requires at least one categorical feature"
            )

        corruption_seed = (seed + 104729) % (2**32)
        corruption = inject_synthetic_corruption(
            X_train,
            rate=float(corruption_rate),
            seed=corruption_seed,
            defects=["categorical_inconsistency"],
        )
        defect_info = corruption.ground_truth["defects"]["categorical_inconsistency"]
        if defect_info["status"] != "completed":
            raise ValueError(
                "categorical corruption could not be injected: "
                + str(defect_info.get("skipped_reason") or "no eligible cells")
            )

        cleaning_request = {
            "drop_exact_duplicates": False,
            "fill_numeric_median": [],
            "fill_categorical_mode": [],
            "trim_whitespace": categorical_columns,
            "lowercase_categories": categorical_columns,
        }
        cleaned_training, cleaning_result = dataset_cleaning._transform(
            corruption.frame, cleaning_request
        )

        test_reference = X_test.copy(deep=True)
        test_reference[target_column] = y_test
        test_fingerprint = _frame_sha256(test_reference)
        test_snapshot = test_reference.copy(deep=True)

        training_conditions = {
            "clean": X_train,
            "corrupted": corruption.frame,
            "cleaned_corrupted": cleaned_training,
        }
        condition_results: dict[str, Any] = {}
        for condition_name in condition_names:
            condition_results[condition_name] = _fit_condition(
                training_conditions[condition_name],
                X_test,
                y_train,
                y_test,
                numeric_columns,
                categorical_columns,
                seed,
            )

        pd.testing.assert_frame_equal(test_reference, test_snapshot)
        if _frame_sha256(test_reference) != test_fingerprint:
            raise RuntimeError("the clean test partition changed during the experiment")

        per_seed.append(
            {
                "seed": seed,
                "corruption_seed": corruption_seed,
                "split": {
                    "strategy": "stratified_random_holdout",
                    "test_size": float(test_size),
                    "train_rows": int(len(X_train)),
                    "test_rows": int(len(X_test)),
                    "clean_test_sha256": test_fingerprint,
                    "test_partition_untouched": True,
                },
                "training_features": {
                    "numeric_columns_inferred_from_clean_training": numeric_columns,
                    "categorical_columns_inferred_from_clean_training": categorical_columns,
                },
                "corruption": {
                    "defect_type": "categorical_inconsistency",
                    "rate": float(corruption_rate),
                    "injected_count": int(defect_info["injected_count"]),
                    "cell_labels": corruption.ground_truth["cell_labels"],
                },
                "cleaning": {
                    "operations": [
                        {
                            "operation": "trim_whitespace",
                            "columns": categorical_columns,
                        },
                        {
                            "operation": "lowercase_categories",
                            "columns": categorical_columns,
                        },
                    ],
                    "changed": bool(cleaning_result["changed"]),
                    "rows_before": int(cleaning_result["rows_before"]),
                    "rows_after": int(cleaning_result["rows_after"]),
                },
                "conditions": condition_results,
            }
        )

    aggregates = {
        condition_name: aggregate_seed_metrics(
            [
                {
                    "seed": run["seed"],
                    "metrics": run["conditions"][condition_name]["metrics"],
                }
                for run in per_seed
            ]
        )
        for condition_name in condition_names
    }
    paired_deltas = aggregate_seed_metrics(
        [
            {
                "seed": run["seed"],
                "metrics": {
                    "cleaned_minus_corrupted_macro_f1": (
                        run["conditions"]["cleaned_corrupted"]["metrics"]["macro_f1"]
                        - run["conditions"]["corrupted"]["metrics"]["macro_f1"]
                    )
                },
            }
            for run in per_seed
        ]
    )

    pd.testing.assert_frame_equal(frame, source)
    return {
        "schema_version": 1,
        "task_type": "classification",
        "model": "logistic_regression",
        "target_column": target_column,
        "source_sha256": _frame_sha256(frame),
        "configuration": {
            "seeds": list(normalized_seeds),
            "test_size": float(test_size),
            "corruption_rate": float(corruption_rate),
            "corruption_defect": "categorical_inconsistency",
            "model_parameters": {
                "max_iter": 1000,
                "class_weight": "balanced",
                "solver": "lbfgs",
            },
        },
        "aggregates": aggregates,
        "paired_cleaned_minus_corrupted_macro_f1": paired_deltas,
        "per_seed": per_seed,
        "method_notes": [
            "Each seed creates one stratified holdout from the untouched clean reference before any corruption.",
            "Only training feature rows are corrupted; the target column and clean test partition are never modified.",
            "The same clean test rows are used for clean, corrupted, and cleaned-corrupted training within each seed.",
            "Numeric/categorical feature inference uses clean training rows only; every fitted imputer, scaler, and encoder is fitted inside a pipeline on the condition-specific training partition only.",
            "The cleaned-corrupted condition applies DataSentry's production whitespace-trim and lowercase operations to training categorical features only.",
            "The classifier is the same class-weighted logistic-regression baseline used by the production modeling service.",
            "The experiment evaluates categorical case/whitespace inconsistency on one public reference dataset; it does not establish generalization to other datasets or defect types.",
            "Seed-level metrics are retained; aggregates use arithmetic mean and sample standard deviation (ddof=1).",
            "The source DataFrame and clean test partition are checked for mutation.",
        ],
    }
