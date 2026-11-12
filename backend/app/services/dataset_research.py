"""Seeded synthetic corruption and detector-evaluation primitives.

These utilities operate on in-memory DataFrame copies. They do not persist files,
modify uploaded datasets, or claim that synthetic defects represent real-world rates.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from statistics import mean, stdev
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

SUPPORTED_DEFECTS = (
    "missingness",
    "duplicates",
    "categorical_inconsistency",
    "invalid_values",
    "numerical_anomalies",
)
NUMERIC_MIN_VALID = 4
NUMERIC_PARSEABILITY = 0.80
INVALID_NUMERIC_TOKEN = "__DATASENTRY_INVALID_NUMERIC__"
MAX_CORRUPTION_RATE = 0.50
MINIMUM_AGGREGATE_SEEDS = 3


@dataclass(frozen=True)
class CorruptionResult:
    """A corrupted copy and exact injected-defect labels."""

    frame: pd.DataFrame
    ground_truth: dict[str, Any]


def _validate_input(
    frame: pd.DataFrame,
    rate: float,
    seed: int,
    defects: Iterable[str] | None,
) -> tuple[float, int, tuple[str, ...]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("frame must be a non-empty pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("frame must have unique column names")
    if any(not isinstance(name, str) or not name.strip() for name in frame.columns):
        raise ValueError("all column names must be non-empty strings")
    if isinstance(rate, (bool, np.bool_)) or not isinstance(
        rate, (int, float, np.integer, np.floating)
    ):
        raise ValueError("rate must be a finite number greater than 0 and at most 0.5")
    numeric_rate = float(rate)
    if not isfinite(numeric_rate) or not 0 < numeric_rate <= MAX_CORRUPTION_RATE:
        raise ValueError("rate must be greater than 0 and at most 0.5")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)):
        raise ValueError("seed must be an integer between 0 and 4294967295")
    numeric_seed = int(seed)
    if not 0 <= numeric_seed <= 4_294_967_295:
        raise ValueError("seed must be an integer between 0 and 4294967295")

    if defects is None:
        selected = SUPPORTED_DEFECTS
    else:
        if isinstance(defects, str):
            raise ValueError("defects must be a sequence of supported defect names")
        selected = tuple(defects)
    if not selected:
        raise ValueError("select at least one corruption type")
    if len(selected) != len(set(selected)):
        raise ValueError("defects must not contain duplicates")
    unknown = [name for name in selected if name not in SUPPORTED_DEFECTS]
    if unknown:
        raise ValueError(f"unsupported corruption type(s): {', '.join(unknown)}")
    return numeric_rate, numeric_seed, tuple(selected)


def _numeric_values(series: pd.Series) -> np.ndarray:
    parsed = pd.to_numeric(series, errors="coerce")
    return parsed.to_numpy(dtype=float, na_value=np.nan)


def _infer_numeric_columns(frame: pd.DataFrame) -> tuple[list[str], dict[str, np.ndarray]]:
    names: list[str] = []
    values_by_column: dict[str, np.ndarray] = {}
    for name in frame.columns:
        values = _numeric_values(frame[name])
        valid_count = int(np.isfinite(values).sum())
        observed_count = int(frame[name].notna().sum())
        ratio = valid_count / observed_count if observed_count else 0.0
        if valid_count >= NUMERIC_MIN_VALID and ratio >= NUMERIC_PARSEABILITY:
            names.append(name)
            values_by_column[name] = values
    return names, values_by_column


def _target_count(candidate_count: int, rate: float) -> int:
    if candidate_count <= 0:
        return 0
    return min(candidate_count, max(1, int(ceil(candidate_count * rate))))


def _sample_cells(
    candidates: list[tuple[int, str]],
    rate: float,
    rng: np.random.Generator,
) -> list[tuple[int, str]]:
    count = _target_count(len(candidates), rate)
    if count == 0:
        return []
    selected_indices = sorted(
        int(index) for index in rng.choice(len(candidates), size=count, replace=False)
    )
    return [candidates[index] for index in selected_indices]


def _cell_candidates(
    frame: pd.DataFrame,
    columns: Sequence[str],
    reserved_rows: set[int],
    reserved_cells: set[tuple[int, str]],
) -> list[tuple[int, str]]:
    positions = {name: index for index, name in enumerate(frame.columns)}
    candidates: list[tuple[int, str]] = []
    for row_index in range(len(frame)):
        if row_index in reserved_rows:
            continue
        for name in columns:
            if (row_index, name) in reserved_cells:
                continue
            if not pd.isna(frame.iat[row_index, positions[name]]):
                candidates.append((row_index, name))
    return candidates


def _high_anomaly_value(values: np.ndarray) -> float | None:
    finite_values = values[np.isfinite(values)]
    if len(finite_values) < NUMERIC_MIN_VALID:
        return None
    maximum = float(np.max(finite_values))
    q1, q3 = np.quantile(finite_values, [0.25, 0.75])
    scale = max(
        float(q3 - q1),
        abs(float(q1)) * 0.1,
        abs(float(q3)) * 0.1,
        1.0,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        step = max(scale * 10.0, 1.0)
        candidate = maximum + step
        if not np.isfinite(candidate):
            candidate = maximum + (np.finfo(np.float64).max - maximum) / 2.0
    if not np.isfinite(candidate) or candidate <= maximum:
        return None
    return float(candidate)


def _unique_invalid_token(frame: pd.DataFrame) -> str:
    existing = {
        str(value)
        for value in frame.to_numpy(dtype=object).ravel()
        if not pd.isna(value)
    }
    token = INVALID_NUMERIC_TOKEN
    suffix = 0
    while token in existing:
        suffix += 1
        token = f"{INVALID_NUMERIC_TOKEN}_{suffix}"
    return token


def inject_synthetic_corruption(
    frame: pd.DataFrame,
    *,
    rate: float = 0.05,
    seed: int = 42,
    defects: Iterable[str] | None = None,
) -> CorruptionResult:
    """Return a deterministic corrupted copy and exact cell/row ground truth.

    The rate is the target fraction of currently eligible units for each defect:
    cells for cell-level defects and source rows for duplicate insertion. The
    target count is rounded up, with at least one unit when candidates exist.
    Duplicate source rows are reserved before cell corruption so each appended
    duplicate is an exact copy of an otherwise unchanged source row.
    """
    rate, seed, selected_defects = _validate_input(frame, rate, seed, defects)
    original = frame.reset_index(drop=True).copy(deep=True)
    working = original.astype(object).copy(deep=True)
    rng = np.random.default_rng(seed)
    row_count = len(original)
    numeric_columns, numeric_values = _infer_numeric_columns(original)
    categorical_columns = [
        name
        for name in original.columns
        if name not in numeric_columns
        and any(
            isinstance(value, str) and bool(value.strip())
            for value in original[name].dropna().tolist()
        )
    ]

    details: dict[str, dict[str, Any]] = {
        name: {
            "status": "not_selected",
            "injected_count": 0,
            "records": [],
            "skipped_reason": None,
        }
        for name in SUPPORTED_DEFECTS
    }
    reserved_rows: set[int] = set()
    reserved_cells: set[tuple[int, str]] = set()
    cell_labels: list[dict[str, Any]] = []
    duplicate_sources: list[int] = []
    duplicate_records: list[dict[str, Any]] = []
    invalid_token: str | None = None

    if "duplicates" in selected_defects:
        duplicate_count = _target_count(row_count, rate)
        duplicate_sources = sorted(
            int(index)
            for index in rng.choice(row_count, size=duplicate_count, replace=False)
        ) if duplicate_count else []
        reserved_rows.update(duplicate_sources)
        duplicate_records = [
            {
                "defect_type": "duplicates",
                "row_index": row_count + offset,
                "data_row_number": row_count + offset + 1,
                "source_row_index": source_index,
                "source_data_row_number": source_index + 1,
            }
            for offset, source_index in enumerate(duplicate_sources)
        ]
        details["duplicates"] = {
            "status": "completed" if duplicate_records else "skipped",
            "injected_count": len(duplicate_records),
            "records": duplicate_records,
            "skipped_reason": None if duplicate_records else "no source rows were eligible",
        }

    def record_cells(defect_type: str, cells: list[tuple[int, str]]) -> None:
        records = [
            {
                "defect_type": defect_type,
                "row_index": row_index,
                "data_row_number": row_index + 1,
                "column": column,
            }
            for row_index, column in cells
        ]
        cell_labels.extend(records)
        reserved_cells.update(cells)
        details[defect_type] = {
            "status": "completed" if records else "skipped",
            "injected_count": len(records),
            "records": records,
            "skipped_reason": None if records else "no eligible cells were available",
        }

    if "missingness" in selected_defects:
        candidates = _cell_candidates(
            original, list(original.columns), reserved_rows, reserved_cells
        )
        cells = _sample_cells(candidates, rate, rng)
        for row_index, column in cells:
            working.iat[row_index, original.columns.get_loc(column)] = pd.NA
        record_cells("missingness", cells)

    if "categorical_inconsistency" in selected_defects:
        candidates = [
            (row_index, column)
            for row_index, column in _cell_candidates(
                original, categorical_columns, reserved_rows, reserved_cells
            )
            if isinstance(original.iat[row_index, original.columns.get_loc(column)], str)
            and bool(original.iat[row_index, original.columns.get_loc(column)].strip())
        ]
        cells = _sample_cells(candidates, rate, rng)
        for row_index, column in cells:
            original_value = str(
                original.iat[row_index, original.columns.get_loc(column)]
            ).strip()
            working.iat[row_index, original.columns.get_loc(column)] = (
                f" {original_value.swapcase()} "
            )
        record_cells("categorical_inconsistency", cells)

    if "invalid_values" in selected_defects:
        candidates = _cell_candidates(
            original, numeric_columns, reserved_rows, reserved_cells
        )
        candidates = [
            (row_index, column)
            for row_index, column in candidates
            if np.isfinite(numeric_values[column][row_index])
        ]
        cells = _sample_cells(candidates, rate, rng)
        if cells:
            invalid_token = _unique_invalid_token(original)
            for row_index, column in cells:
                working[column] = working[column].astype(object)
                working.iat[row_index, original.columns.get_loc(column)] = invalid_token
        record_cells("invalid_values", cells)

    if "numerical_anomalies" in selected_defects:
        anomaly_values = {
            name: _high_anomaly_value(numeric_values[name])
            for name in numeric_columns
        }
        eligible_columns = [
            name for name, value in anomaly_values.items() if value is not None
        ]
        candidates = _cell_candidates(
            original, eligible_columns, reserved_rows, reserved_cells
        )
        candidates = [
            (row_index, column)
            for row_index, column in candidates
            if np.isfinite(numeric_values[column][row_index])
        ]
        cells = _sample_cells(candidates, rate, rng)
        for row_index, column in cells:
            working[column] = working[column].astype(object)
            working.iat[row_index, original.columns.get_loc(column)] = anomaly_values[column]
        record_cells("numerical_anomalies", cells)
        if not cells:
            details["numerical_anomalies"]["skipped_reason"] = (
                "no eligible numeric column had room for a finite value above its maximum"
            )

    if duplicate_sources:
        duplicate_frame = original.iloc[duplicate_sources].astype(object).copy(deep=True)
        working = pd.concat([working, duplicate_frame], ignore_index=True)

    cell_labels.sort(
        key=lambda item: (item["row_index"], item["column"], item["defect_type"])
    )
    row_label_map: dict[int, set[str]] = {}
    for label in cell_labels:
        row_label_map.setdefault(label["row_index"], set()).add(label["defect_type"])
    for record in duplicate_records:
        row_label_map.setdefault(record["row_index"], set()).add("duplicates")
    row_labels = [
        {
            "row_index": row_index,
            "data_row_number": row_index + 1,
            "defect_types": [
                defect for defect in SUPPORTED_DEFECTS if defect in defect_types
            ],
        }
        for row_index, defect_types in sorted(row_label_map.items())
    ]

    ground_truth = {
        "schema_version": 1,
        "seed": seed,
        "rate": rate,
        "selected_defects": list(selected_defects),
        "source_shape": {"rows": int(row_count), "columns": int(original.shape[1])},
        "corrupted_shape": {"rows": int(len(working)), "columns": int(working.shape[1])},
        "numeric_columns_used": numeric_columns,
        "categorical_columns_used": categorical_columns,
        "invalid_value_token": invalid_token,
        "label_convention": {
            "row_index": "zero-based position in the returned corrupted frame",
            "data_row_number": "one-based data row number, excluding the CSV header",
            "duplicates": "only the newly appended duplicate row is labeled; its source row is recorded separately",
            "cell_labels": "one record per injected cell defect",
        },
        "rate_semantics": (
            "fraction of currently eligible cells for cell defects and eligible source rows "
            "for duplicate insertion; rounded up to at least one when candidates exist"
        ),
        "defects": details,
        "cell_labels": cell_labels,
        "duplicate_rows": duplicate_records,
        "row_labels": row_labels,
    }
    return CorruptionResult(frame=working.reset_index(drop=True), ground_truth=ground_truth)


def _binary_array(values: Sequence[int | bool], name: str) -> np.ndarray:
    array = np.asarray(list(values))
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional sequence")
    if not bool(np.isin(array, [0, 1, False, True]).all()):
        raise ValueError(f"{name} values must be boolean or binary 0/1")
    return array.astype(bool)


def evaluate_binary_detector(
    ground_truth: Sequence[int | bool],
    predictions: Sequence[int | bool],
) -> dict[str, Any]:
    """Calculate binary precision, recall, F1, accuracy, and confusion counts.

    Undefined precision/recall/F1 denominators use the explicit zero convention.
    """
    truth = _binary_array(ground_truth, "ground_truth")
    predicted = _binary_array(predictions, "predictions")
    if len(truth) != len(predicted):
        raise ValueError("ground_truth and predictions must have equal lengths")

    true_positive = int(np.count_nonzero(truth & predicted))
    false_positive = int(np.count_nonzero(~truth & predicted))
    true_negative = int(np.count_nonzero(~truth & ~predicted))
    false_negative = int(np.count_nonzero(truth & ~predicted))
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (true_positive + true_negative) / len(truth)
    return {
        "support": int(np.count_nonzero(truth)),
        "predicted_positive_count": int(np.count_nonzero(predicted)),
        "confusion_counts": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
        },
        "precision": round(float(precision), 6),
        "recall": round(float(recall), 6),
        "f1": round(float(f1), 6),
        "accuracy": round(float(accuracy), 6),
        "zero_division_convention": 0,
    }


def aggregate_seed_metrics(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate identical numeric metrics across at least three distinct seeds.

    Standard deviation is the sample standard deviation (ddof=1), not population SD.
    """
    if len(runs) < MINIMUM_AGGREGATE_SEEDS:
        raise ValueError(
            f"at least {MINIMUM_AGGREGATE_SEEDS} distinct seeded runs are required"
        )
    seeds: list[int] = []
    metric_names: set[str] | None = None
    metric_values: dict[str, list[float]] = {}

    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("each run must be a mapping with seed and metrics")
        seed = run.get("seed")
        if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)):
            raise ValueError("each run seed must be an integer")
        seed = int(seed)
        if seed < 0 or seed > 4_294_967_295 or seed in seeds:
            raise ValueError("run seeds must be distinct integers between 0 and 4294967295")
        seeds.append(seed)

        metrics = run.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            raise ValueError("each run must contain a non-empty metrics mapping")
        current_names = set(metrics)
        if any(not isinstance(name, str) or not name for name in current_names):
            raise ValueError("metric names must be non-empty strings")
        if metric_names is None:
            metric_names = current_names
            metric_values = {name: [] for name in sorted(metric_names)}
        elif current_names != metric_names:
            raise ValueError("all runs must report the same metric names")

        for name in sorted(metric_names):
            value = metrics[name]
            if isinstance(value, (bool, np.bool_)):
                raise ValueError(f"metric '{name}' must be a finite number")
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"metric '{name}' must be a finite number") from exc
            if not isfinite(numeric_value):
                raise ValueError(f"metric '{name}' must be a finite number")
            metric_values[name].append(numeric_value)

    aggregated = {
        name: {
            "values": [round(value, 6) for value in values],
            "mean": round(float(mean(values)), 6),
            "sample_standard_deviation": round(float(stdev(values)), 6),
        }
        for name, values in metric_values.items()
    }
    return {
        "seed_count": len(seeds),
        "seeds": seeds,
        "aggregation": "arithmetic mean and sample standard deviation (ddof=1)",
        "metrics": aggregated,
    }
