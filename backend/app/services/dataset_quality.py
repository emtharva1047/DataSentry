"""Read-only data-quality rules and explainable Data Quality Score."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from ..models import Dataset
from . import dataset_ingestion

NUMERIC_LIKE_MIN_RATIO = 0.8
MIN_NUMERIC_VALUES = 2
EVIDENCE_ROW_LIMIT = 20
DQS_WEIGHTS = {
    "completeness": 0.30,
    "validity": 0.30,
    "uniqueness": 0.20,
    "consistency": 0.20,
}


class DatasetQualityFileUnavailableError(RuntimeError):
    """Raised when a stored dataset file is missing, unsafe, or unreadable."""


def _row_numbers(indexes: list[int] | pd.Index) -> list[int]:
    """Return one-based data-row numbers (the header is not counted)."""
    return [int(index) + 1 for index in list(indexes)[:EVIDENCE_ROW_LIMIT]]


def _severity(affected: int, denominator: int) -> str:
    """Assign a transparent severity band from the affected-cell/row rate."""
    rate = affected / denominator if denominator else 0.0
    if rate >= 0.20:
        return "high"
    if rate >= 0.05:
        return "medium"
    return "low"


def _issue(
    code: str,
    scope: str,
    column: str | None,
    affected: int,
    denominator: int,
    message: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "scope": scope,
        "column": column,
        "severity": _severity(affected, denominator),
        "affected_count": int(affected),
        "denominator": int(denominator),
        "affected_pct": round((affected / denominator) * 100, 2) if denominator else 0.0,
        "message": message,
        "evidence": evidence,
    }


def _read_dataset(dataset: Dataset) -> pd.DataFrame:
    upload_root = dataset_ingestion.UPLOAD_DIR.resolve()
    try:
        source_path = Path(dataset.original_path).resolve(strict=True)
        source_path.relative_to(upload_root)
    except (OSError, ValueError) as exc:
        raise DatasetQualityFileUnavailableError(
            "The stored dataset file is unavailable or outside the upload directory."
        ) from exc

    try:
        # Keep strings intact so whitespace and case inconsistencies remain observable.
        return pd.read_csv(source_path, encoding=dataset.encoding, dtype=str)
    except (OSError, UnicodeDecodeError, EmptyDataError, ParserError, ValueError) as exc:
        raise DatasetQualityFileUnavailableError(
            "The stored CSV could not be read for quality assessment."
        ) from exc


def _numeric_candidates(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Infer numeric-like columns conservatively; do not impose business ranges."""
    candidates: dict[str, dict[str, Any]] = {}
    for name in frame.columns:
        non_null = frame[name].dropna().astype(str).str.strip()
        if non_null.empty:
            continue
        parsed = pd.to_numeric(non_null, errors="coerce")
        finite = pd.Series(
            np.isfinite(parsed.to_numpy(dtype=float)),
            index=parsed.index,
        )
        valid = parsed.notna() & finite
        valid_count = int(valid.sum())
        ratio = valid_count / len(non_null)
        if valid_count >= MIN_NUMERIC_VALUES and ratio >= NUMERIC_LIKE_MIN_RATIO:
            invalid_indexes = non_null.index[~valid]
            candidates[str(name)] = {
                "valid_count": valid_count,
                "denominator": int(len(non_null)),
                "invalid_indexes": invalid_indexes,
            }
    return candidates


def _categorical_findings(series: pd.Series) -> dict[str, Any]:
    non_null = series.dropna().astype(str)
    trimmed = non_null.str.strip()
    whitespace_indexes = set(non_null.index[non_null != trimmed])
    groups: dict[str, dict[str, list[int]]] = {}

    for index, value in trimmed.items():
        key = value.casefold()
        groups.setdefault(key, {}).setdefault(value, []).append(int(index))

    case_variant_groups = []
    case_variant_indexes: set[int] = set()
    for normalized, variants in groups.items():
        if len(variants) <= 1:
            continue
        for indexes in variants.values():
            case_variant_indexes.update(indexes)
        case_variant_groups.append(
            {
                "normalized_value": normalized,
                "variants": [
                    {"value": value, "count": len(indexes)}
                    for value, indexes in sorted(variants.items())
                ],
            }
        )

    inconsistent_indexes = whitespace_indexes | case_variant_indexes
    return {
        "denominator": int(len(non_null)),
        "inconsistent_indexes": inconsistent_indexes,
        "whitespace_indexes": whitespace_indexes,
        "case_variant_groups": case_variant_groups[:EVIDENCE_ROW_LIMIT],
    }


def _component(
    score: float | None,
    weight: float,
    numerator: int,
    denominator: int,
    applicable: bool,
    basis: str,
) -> dict[str, Any]:
    return {
        "score": round(score, 2) if score is not None else None,
        "weight": weight,
        "applicable": applicable,
        "numerator": int(numerator),
        "denominator": int(denominator),
        "basis": basis,
    }


def assess_dataset_quality(dataset: Dataset) -> dict[str, Any]:
    """Run deterministic, read-only quality checks and calculate the DQS."""
    frame = _read_dataset(dataset)
    row_count, column_count = frame.shape
    total_cells = int(row_count * column_count)
    missing_cells = int(frame.isna().sum().sum())
    issues: list[dict[str, Any]] = []

    # Completeness: report missing values separately for each column.
    for name in frame.columns:
        missing_indexes = frame.index[frame[name].isna()]
        missing_count = len(missing_indexes)
        if missing_count:
            issues.append(
                _issue(
                    "missing_values",
                    "column",
                    str(name),
                    missing_count,
                    row_count,
                    f"{missing_count} of {row_count} rows are missing a value in '{name}'.",
                    {"row_numbers": _row_numbers(missing_indexes)},
                )
            )

    # Uniqueness: count duplicate occurrences after the first copy of each row.
    duplicate_mask = frame.duplicated(keep="first")
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        all_duplicate_mask = frame.duplicated(keep=False)
        duplicate_groups = int(
            frame.loc[all_duplicate_mask].drop_duplicates().shape[0]
        )
        duplicate_indexes = frame.index[duplicate_mask]
        issues.append(
            _issue(
                "duplicate_rows",
                "dataset",
                None,
                duplicate_count,
                row_count,
                f"{duplicate_count} rows repeat an earlier complete row across {duplicate_groups} duplicate groups.",
                {
                    "row_numbers": _row_numbers(duplicate_indexes),
                    "duplicate_group_count": duplicate_groups,
                    "comparison": "exact across all columns; first occurrence is retained",
                },
            )
        )

    # Validity: infer numeric-like columns only when at least 80% of non-null
    # values parse as finite numbers. This detects likely type drift without
    # inventing domain constraints such as minimum/maximum business values.
    numeric = _numeric_candidates(frame)
    numeric_valid = sum(item["valid_count"] for item in numeric.values())
    numeric_denominator = sum(item["denominator"] for item in numeric.values())
    for name, finding in numeric.items():
        invalid_indexes = finding["invalid_indexes"]
        invalid_count = len(invalid_indexes)
        if invalid_count:
            issues.append(
                _issue(
                    "type_mismatch",
                    "column",
                    name,
                    invalid_count,
                    finding["denominator"],
                    f"{invalid_count} non-missing values in '{name}' do not match its inferred numeric type.",
                    {"row_numbers": _row_numbers(invalid_indexes), "expected_type": "numeric"},
                )
            )

    # Consistency: inspect non-numeric-like columns for surrounding whitespace
    # and values that differ only by letter case. Findings require human review.
    categorical_denominator = 0
    categorical_inconsistent = 0
    for name in frame.columns:
        if str(name) in numeric:
            continue
        finding = _categorical_findings(frame[name])
        denominator = finding["denominator"]
        if denominator == 0:
            continue
        categorical_denominator += denominator
        inconsistent_indexes = finding["inconsistent_indexes"]
        affected = len(inconsistent_indexes)
        categorical_inconsistent += affected
        if affected:
            issues.append(
                _issue(
                    "categorical_inconsistency",
                    "column",
                    str(name),
                    affected,
                    denominator,
                    f"{affected} values in '{name}' contain surrounding whitespace or case-only category variants.",
                    {
                        "row_numbers": _row_numbers(sorted(inconsistent_indexes)),
                        "whitespace_row_numbers": _row_numbers(
                            sorted(finding["whitespace_indexes"])
                        ),
                        "case_variant_groups": finding["case_variant_groups"],
                        "review_required": True,
                        "automatic_normalization": False,
                    },
                )
            )

    completeness_numerator = total_cells - missing_cells
    uniqueness_numerator = row_count - duplicate_count
    consistency_numerator = categorical_denominator - categorical_inconsistent

    components = {
        "completeness": _component(
            completeness_numerator / total_cells * 100 if total_cells else None,
            DQS_WEIGHTS["completeness"],
            completeness_numerator,
            total_cells,
            total_cells > 0,
            "non-missing cells / all cells",
        ),
        "validity": _component(
            numeric_valid / numeric_denominator * 100 if numeric_denominator else None,
            DQS_WEIGHTS["validity"],
            numeric_valid,
            numeric_denominator,
            numeric_denominator > 0,
            "finite, parseable values / non-missing values in inferred numeric columns",
        ),
        "uniqueness": _component(
            uniqueness_numerator / row_count * 100 if row_count else None,
            DQS_WEIGHTS["uniqueness"],
            uniqueness_numerator,
            row_count,
            row_count > 0,
            "rows excluding duplicate occurrences / all rows",
        ),
        "consistency": _component(
            consistency_numerator / categorical_denominator * 100
            if categorical_denominator
            else None,
            DQS_WEIGHTS["consistency"],
            consistency_numerator,
            categorical_denominator,
            categorical_denominator > 0,
            "categorical values without detected whitespace/case inconsistency / non-missing categorical values",
        ),
    }

    active_weight_total = sum(
        item["weight"] for item in components.values() if item["applicable"]
    )
    overall = None
    if active_weight_total:
        overall = round(
            sum(
                item["score"] * item["weight"]
                for item in components.values()
                if item["applicable"] and item["score"] is not None
            )
            / active_weight_total,
            2,
        )

    severity_counts = {
        level: sum(issue["severity"] == level for issue in issues)
        for level in ("high", "medium", "low")
    }
    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "quality_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shape": {"rows": int(row_count), "columns": int(column_count)},
        "issue_count": len(issues),
        "issues_by_severity": severity_counts,
        "issues": issues,
        "data_quality_score": {
            "overall": overall,
            "scale": "0-100",
            "active_weight_total": round(active_weight_total, 2),
            "weighting": "weighted mean of applicable components; active weights are renormalized",
            "components": components,
        },
        "method_notes": [
            "Missing-value behavior follows pandas CSV parsing defaults.",
            "Numeric validity uses an inferred numeric-like threshold of at least 80% parseable finite non-missing values and at least two valid values.",
            "Business-specific domain constraints are not inferred; configure an expected schema before treating values outside business ranges as invalid.",
            "Whitespace and case-only category variants are review flags, not proof of an error; no values are changed.",
            "Exact duplicates count every repeated occurrence after the first; no row is deleted.",
            "Anomaly detection is separate from this score.",
        ],
    }
