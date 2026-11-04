"""Read-only, reproducible numerical anomaly detection."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sklearn.ensemble import IsolationForest

from ..models import Dataset
from . import dataset_ingestion

NUMERIC_MIN_VALID = 4
NUMERIC_MIN_RATIO = 0.80
ISOLATION_MIN_ROWS = 10
MODIFIED_Z_SCALE = 0.6744897501960817


class DatasetAnomalyFileUnavailableError(RuntimeError):
    """Raised when a stored source file is missing, unsafe, or unreadable."""


class DatasetAnomalyRequestError(ValueError):
    """Raised when requested anomaly columns are not present in the dataset."""


def _read_dataset(dataset: Dataset) -> pd.DataFrame:
    """Read the stored CSV as text while enforcing the upload-directory boundary."""
    upload_root = dataset_ingestion.UPLOAD_DIR.resolve()
    try:
        source_path = Path(dataset.original_path).resolve(strict=True)
        source_path.relative_to(upload_root)
    except (OSError, ValueError) as exc:
        raise DatasetAnomalyFileUnavailableError(
            "The stored dataset file is unavailable or outside the upload directory."
        ) from exc

    try:
        return pd.read_csv(source_path, encoding=dataset.encoding, dtype=str)
    except (OSError, UnicodeDecodeError, EmptyDataError, ParserError, ValueError) as exc:
        raise DatasetAnomalyFileUnavailableError(
            "The stored CSV could not be read for anomaly detection."
        ) from exc


def _safe_float(value: float, digits: int = 8) -> float | None:
    """Convert finite numerical results to JSON-safe Python floats."""
    number = float(value)
    return round(number, digits) if np.isfinite(number) else None


def _numeric_candidates(
    frame: pd.DataFrame,
    requested_columns: list[str] | None,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    """Select numeric-like columns without silently coercing source values."""
    names = requested_columns if requested_columns is not None else [str(name) for name in frame.columns]
    missing_names = [name for name in names if name not in frame.columns]
    if missing_names:
        raise DatasetAnomalyRequestError(
            "Unknown dataset column(s): " + ", ".join(missing_names[:10])
        )

    candidates: dict[str, np.ndarray] = {}
    diagnostics: list[dict[str, Any]] = []
    for name in names:
        parsed = pd.to_numeric(frame[name], errors="coerce")
        values = parsed.to_numpy(dtype=float, na_value=np.nan)
        finite_mask = np.isfinite(values)
        non_missing_count = int(frame[name].notna().sum())
        valid_count = int(finite_mask.sum())
        ratio = valid_count / non_missing_count if non_missing_count else 0.0
        eligible = valid_count >= NUMERIC_MIN_VALID and ratio >= NUMERIC_MIN_RATIO
        reason = None
        if non_missing_count == 0:
            reason = "column has no non-missing values"
        elif valid_count < NUMERIC_MIN_VALID:
            reason = f"fewer than {NUMERIC_MIN_VALID} finite numeric values"
        elif ratio < NUMERIC_MIN_RATIO:
            reason = f"finite numeric parseability is below {NUMERIC_MIN_RATIO:.0%}"
        if eligible:
            candidates[name] = values
        diagnostics.append(
            {
                "column": name,
                "eligible": eligible,
                "valid_count": valid_count,
                "non_missing_count": non_missing_count,
                "parse_failure_count": non_missing_count - valid_count,
                "finite_parseability_pct": round(ratio * 100, 2),
                "reason": reason,
            }
        )
    return candidates, diagnostics


def _row_numbers(indexes: np.ndarray) -> list[int]:
    """Convert zero-based DataFrame indexes to one-based data-row numbers."""
    return [int(index) + 1 for index in indexes.tolist()]


def _run_iqr(
    numeric: dict[str, np.ndarray],
    multiplier: float,
    evidence_limit: int,
) -> tuple[dict[str, Any], set[int]]:
    column_results: list[dict[str, Any]] = []
    all_flagged: set[int] = set()
    for name, values in numeric.items():
        indexes = np.flatnonzero(np.isfinite(values))
        finite_values = values[indexes]
        reference_scale = float(np.max(np.abs(finite_values))) if finite_values.size else 1.0
        if reference_scale == 0.0:
            reference_scale = 1.0
        normalized = finite_values / reference_scale
        q1_norm, q3_norm = np.quantile(normalized, [0.25, 0.75])
        iqr_norm = float(q3_norm - q1_norm)
        lower_norm = float(q1_norm - multiplier * iqr_norm)
        upper_norm = float(q3_norm + multiplier * iqr_norm)
        flagged_positions = np.flatnonzero((normalized < lower_norm) | (normalized > upper_norm))
        flagged_indexes = indexes[flagged_positions]
        all_flagged.update(int(index) for index in flagged_indexes)

        distances = np.maximum(lower_norm - normalized, normalized - upper_norm)
        order = sorted(
            flagged_positions.tolist(),
            key=lambda position: (-float(distances[position]), int(indexes[position])),
        )
        evidence = [
            {
                "row_number": int(indexes[position]) + 1,
                "value": _safe_float(finite_values[position]),
                "distance_beyond_fence": _safe_float(distances[position] * reference_scale),
            }
            for position in order[:evidence_limit]
        ]
        column_results.append(
            {
                "column": name,
                "status": "completed",
                "valid_count": int(len(finite_values)),
                "q1": _safe_float(q1_norm * reference_scale),
                "q3": _safe_float(q3_norm * reference_scale),
                "iqr": _safe_float(iqr_norm * reference_scale),
                "lower_fence": _safe_float(lower_norm * reference_scale),
                "upper_fence": _safe_float(upper_norm * reference_scale),
                "flagged_count": int(len(flagged_indexes)),
                "flagged_row_numbers": _row_numbers(flagged_indexes)[:evidence_limit],
                "flagged_row_numbers_truncated": len(flagged_indexes) > evidence_limit,
                "evidence": evidence,
                "evidence_truncated": len(flagged_indexes) > len(evidence),
            }
        )

    if not column_results:
        return (
            {
                "status": "skipped",
                "reason": "No columns met the numeric eligibility requirements.",
                "columns": [],
                "flagged_row_count": 0,
                "flagged_row_numbers": [],
            },
            all_flagged,
        )
    return (
        {
            "status": "completed",
            "parameters": {"multiplier": multiplier},
            "columns": column_results,
            "flagged_row_count": len(all_flagged),
            "flagged_row_numbers": sorted(index + 1 for index in all_flagged)[:evidence_limit],
            "flagged_row_numbers_truncated": len(all_flagged) > evidence_limit,
        },
        all_flagged,
    )


def _run_robust_zscore(
    numeric: dict[str, np.ndarray],
    threshold: float,
    evidence_limit: int,
) -> tuple[dict[str, Any], set[int]]:
    column_results: list[dict[str, Any]] = []
    all_flagged: set[int] = set()
    completed_columns = 0

    for name, values in numeric.items():
        indexes = np.flatnonzero(np.isfinite(values))
        finite_values = values[indexes]
        reference_scale = float(np.max(np.abs(finite_values))) if finite_values.size else 1.0
        if reference_scale == 0.0:
            reference_scale = 1.0
        normalized = finite_values / reference_scale
        median = float(np.median(normalized))
        mad = float(np.median(np.abs(normalized - median)))
        if mad == 0.0:
            column_results.append(
                {
                    "column": name,
                    "status": "skipped",
                    "reason": "Median absolute deviation is zero; robust Z-scores are undefined.",
                    "valid_count": int(len(finite_values)),
                    "flagged_count": 0,
                    "flagged_row_numbers": [],
                    "evidence": [],
                }
            )
            continue

        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            scores = np.abs(MODIFIED_Z_SCALE * (normalized - median) / mad)
        flagged_positions = np.flatnonzero(scores > threshold)
        flagged_indexes = indexes[flagged_positions]
        all_flagged.update(int(index) for index in flagged_indexes)
        order = sorted(
            flagged_positions.tolist(),
            key=lambda position: (-float(scores[position]), int(indexes[position])),
        )
        evidence = [
            {
                "row_number": int(indexes[position]) + 1,
                "value": _safe_float(finite_values[position]),
                "modified_z_score": _safe_float(scores[position]),
            }
            for position in order[:evidence_limit]
        ]
        column_results.append(
            {
                "column": name,
                "status": "completed",
                "valid_count": int(len(finite_values)),
                "median": _safe_float(median * reference_scale),
                "mad": _safe_float(mad * reference_scale),
                "flagged_count": int(len(flagged_indexes)),
                "flagged_row_numbers": _row_numbers(flagged_indexes)[:evidence_limit],
                "flagged_row_numbers_truncated": len(flagged_indexes) > evidence_limit,
                "evidence": evidence,
                "evidence_truncated": len(flagged_indexes) > len(evidence),
            }
        )
        completed_columns += 1

    status = "completed" if completed_columns else "skipped"
    result: dict[str, Any] = {
        "status": status,
        "columns": column_results,
        "flagged_row_count": len(all_flagged),
        "flagged_row_numbers": sorted(index + 1 for index in all_flagged)[:evidence_limit],
            "flagged_row_numbers_truncated": len(all_flagged) > evidence_limit,
    }
    if completed_columns:
        result["parameters"] = {"modified_z_threshold": threshold}
    else:
        result["reason"] = "No eligible column had a non-zero median absolute deviation."
    return result, all_flagged


def _run_isolation_forest(
    numeric: dict[str, np.ndarray],
    row_count: int,
    contamination: float,
    random_state: int,
    n_estimators: int,
    evidence_limit: int,
) -> tuple[dict[str, Any], set[int]]:
    """Fit a seeded Isolation Forest on median-imputed, robust-scaled numeric data."""
    if not numeric:
        return (
            {
                "status": "skipped",
                "reason": "No columns met the numeric eligibility requirements.",
                "feature_columns": [],
                "rows_scored": 0,
                "flagged_count": 0,
                "flagged_row_numbers": [],
                "evidence": [],
            },
            set(),
        )

    raw_matrix = np.column_stack([numeric[name] for name in numeric])
    observed_rows = np.isfinite(raw_matrix).any(axis=1)
    row_indexes = np.flatnonzero(observed_rows)
    if len(row_indexes) < ISOLATION_MIN_ROWS:
        return (
            {
                "status": "skipped",
                "reason": f"Isolation Forest requires at least {ISOLATION_MIN_ROWS} rows with one or more observed numeric values.",
                "feature_columns": [],
                "rows_scored": int(len(row_indexes)),
                "flagged_count": 0,
                "flagged_row_numbers": [],
                "evidence": [],
            },
            set(),
        )

    raw_observed = raw_matrix[observed_rows]
    scaled_features: list[np.ndarray] = []
    feature_names: list[str] = []
    preprocessing: list[dict[str, Any]] = []

    for feature_index, name in enumerate(numeric):
        column = raw_observed[:, feature_index]
        finite = np.isfinite(column)
        finite_values = column[finite]
        if len(finite_values) < NUMERIC_MIN_VALID:
            continue

        reference_scale = float(np.max(np.abs(finite_values)))
        if reference_scale == 0.0:
            continue
        normalized = finite_values / reference_scale
        center = float(np.median(normalized))
        q1, q3 = np.quantile(normalized, [0.25, 0.75])
        scale = float(q3 - q1)
        scale_method = "iqr"
        if scale == 0.0:
            scale = float(np.median(np.abs(normalized - center)) * 1.4826)
            scale_method = "scaled_mad"
        if scale == 0.0:
            scale = float(np.std(normalized))
            scale_method = "standard_deviation"
        if scale == 0.0 or not np.isfinite(scale):
            continue

        normalized_column = column / reference_scale
        imputed = np.where(finite, normalized_column, center)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            scaled = (imputed - center) / scale
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=1_000_000.0, neginf=-1_000_000.0)
        scaled = np.clip(scaled, -1_000_000.0, 1_000_000.0)
        scaled_features.append(scaled)
        feature_names.append(name)
        preprocessing.append(
            {
                "column": name,
                "imputation": "median",
                "scaling": scale_method,
                "clipped_scaled_values": True,
            }
        )

    if not scaled_features:
        return (
            {
                "status": "skipped",
                "reason": "No non-constant numeric features remained after safe preprocessing.",
                "feature_columns": [],
                "rows_scored": int(len(row_indexes)),
                "flagged_count": 0,
                "flagged_row_numbers": [],
                "evidence": [],
            },
            set(),
        )

    matrix = np.column_stack(scaled_features)
    model = IsolationForest(
        n_estimators=n_estimators,
        max_samples=min(256, len(matrix)),
        contamination=contamination,
        random_state=random_state,
        n_jobs=1,
    )
    predictions = model.fit_predict(matrix)
    anomaly_scores = -model.decision_function(matrix)
    flagged_positions = np.flatnonzero(predictions == -1)
    flagged_indexes = row_indexes[flagged_positions]
    order = sorted(
        flagged_positions.tolist(),
        key=lambda position: (-float(anomaly_scores[position]), int(row_indexes[position])),
    )
    evidence = [
        {
            "row_number": int(row_indexes[position]) + 1,
            "anomaly_score": _safe_float(anomaly_scores[position]),
        }
        for position in order[:evidence_limit]
    ]
    flagged_set = {int(index) for index in flagged_indexes}
    return (
        {
            "status": "completed",
            "parameters": {
                "contamination": contamination,
                "random_state": random_state,
                "n_estimators": n_estimators,
                "max_samples": min(256, len(matrix)),
                "score_direction": "higher scores indicate more anomalous rows",
                "decision_threshold": _safe_float(-model.offset_),
            },
            "feature_columns": feature_names,
            "preprocessing": preprocessing,
            "rows_scored": int(len(row_indexes)),
            "flagged_count": int(len(flagged_indexes)),
            "flagged_row_numbers": _row_numbers(flagged_indexes)[:evidence_limit],
                "flagged_row_numbers_truncated": len(flagged_indexes) > evidence_limit,
            "evidence": evidence,
            "evidence_truncated": len(flagged_indexes) > len(evidence),
        },
        flagged_set,
    )


def detect_dataset_anomalies(dataset: Dataset, request: dict[str, Any]) -> dict[str, Any]:
    """Run selected anomaly detectors without changing the uploaded dataset.

    Anomaly results are review flags, deliberately separate from the Data Quality
    Score. Isolation Forest uses a fixed seed by default and never removes rows.
    """
    frame = _read_dataset(dataset)
    row_count, column_count = frame.shape
    numeric, diagnostics = _numeric_candidates(frame, request.get("columns"))
    detectors: dict[str, Any] = {}
    flagged_by_detector: dict[str, set[int]] = {}

    selected = request["detectors"]
    evidence_limit = int(request["max_evidence_rows"])

    if "iqr" in selected:
        result, flagged = _run_iqr(numeric, float(request["iqr_multiplier"]), evidence_limit)
        detectors["iqr"] = result
        flagged_by_detector["iqr"] = flagged

    if "robust_zscore" in selected:
        result, flagged = _run_robust_zscore(
            numeric, float(request["robust_z_threshold"]), evidence_limit
        )
        detectors["robust_zscore"] = result
        flagged_by_detector["robust_zscore"] = flagged

    if "isolation_forest" in selected:
        result, flagged = _run_isolation_forest(
            numeric,
            row_count,
            float(request["contamination"]),
            int(request["random_state"]),
            int(request["n_estimators"]),
            evidence_limit,
        )
        detectors["isolation_forest"] = result
        flagged_by_detector["isolation_forest"] = flagged

    union_flagged = set().union(*flagged_by_detector.values()) if flagged_by_detector else set()
    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "anomaly_detection_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": dataset.sha256_hash,
        "shape": {"rows": int(row_count), "columns": int(column_count)},
        "numeric_columns": diagnostics,
        "parameters": {
            "detectors": selected,
            "iqr_multiplier": float(request["iqr_multiplier"]),
            "robust_z_threshold": float(request["robust_z_threshold"]),
            "contamination": float(request["contamination"]),
            "random_state": int(request["random_state"]),
            "n_estimators": int(request["n_estimators"]),
            "max_evidence_rows": evidence_limit,
        },
        "detectors": detectors,
        "summary": {
            "flagged_row_count": len(union_flagged),
            "flagged_row_numbers": sorted(index + 1 for index in union_flagged)[:evidence_limit],
            "evidence_truncated": len(union_flagged) > evidence_limit,
            "flagged_count_by_detector": {
                name: len(indexes) for name, indexes in flagged_by_detector.items()
            },
        },
        "method_notes": [
            f"Numeric columns require at least {NUMERIC_MIN_VALID} finite values and {NUMERIC_MIN_RATIO:.0%} finite parseability among non-missing values.",
            "IQR fences are Q1 - multiplier*IQR and Q3 + multiplier*IQR; values outside the fences are review flags.",
            "Robust Z-score is the absolute modified Z-score using 0.67448975*(x - median)/MAD; zero-MAD columns are skipped.",
            "Isolation Forest uses median imputation and robust feature scaling fitted on the analyzed dataset, a bounded max_samples value, and the supplied random seed.",
            "Isolation Forest is an unsupervised diagnostic; its score is not a probability or proof of an invalid record.",
            "Anomaly flags are separate from the Data Quality Score and never modify or delete source rows.",
            "Evidence row numbers are one-based data-row numbers and exclude the CSV header.",
        ],
    }
