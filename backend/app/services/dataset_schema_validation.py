"""Read-only validation against an explicit, caller-supplied dataset schema."""
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from ..models import Dataset
from .dataset_quality import (
    DatasetQualityFileUnavailableError,
    _issue,
    _read_dataset,
    _row_numbers,
)

BOOLEAN_VALUES = {"true", "false", "1", "0", "yes", "no"}


def _typed_values(values: pd.Series, expected_type: str) -> tuple[pd.Series, pd.Series | None]:
    """Return a validity mask and optional numeric parse without coercing source data."""
    if expected_type == "string":
        return pd.Series(True, index=values.index, dtype=bool), None

    if expected_type in {"integer", "number"}:
        parsed = pd.to_numeric(values.str.strip(), errors="coerce")
        finite = pd.Series(
            np.isfinite(parsed.to_numpy(dtype=float)),
            index=parsed.index,
            dtype=bool,
        )
        valid = parsed.notna() & finite
        if expected_type == "integer":
            integral = pd.Series(
                np.isclose(np.mod(parsed.fillna(0).to_numpy(dtype=float), 1), 0),
                index=parsed.index,
                dtype=bool,
            )
            valid &= integral
        return valid, parsed

    normalized = values.str.strip().str.casefold()
    return normalized.isin(BOOLEAN_VALUES), None


def _append_issue(
    issues: list[dict[str, Any]],
    code: str,
    column: str,
    indexes: list[int] | pd.Index,
    denominator: int,
    message: str,
    evidence: dict[str, Any],
) -> None:
    affected = len(indexes)
    issues.append(
        _issue(
            code,
            "column",
            column,
            affected,
            denominator,
            message,
            evidence,
        )
    )


def validate_dataset_schema(dataset: Dataset, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate expected columns, types, required values, ranges, and allowed values.

    The uploaded CSV is read as text and never changed. Numeric and boolean values
    are parsed only for validation; no normalized or cleaned dataset is produced.
    """
    frame = _read_dataset(dataset)
    row_count, column_count = frame.shape
    expected_columns = schema["columns"]
    allow_extra_columns = bool(schema.get("allow_extra_columns", False))
    actual_columns = [str(name) for name in frame.columns]
    expected_names = list(expected_columns)
    issues: list[dict[str, Any]] = []
    present_count = 0

    for name, constraint in expected_columns.items():
        if name not in frame.columns:
            issues.append(
                _issue(
                    "missing_schema_column",
                    "column",
                    name,
                    1,
                    1,
                    f"Expected column '{name}' is not present in the dataset.",
                    {"expected_type": constraint["type"], "required": constraint["required"]},
                )
            )
            continue

        present_count += 1
        series = frame[name]
        missing_indexes = frame.index[series.isna()]
        non_missing = series.dropna().astype(str)

        if constraint["required"] and len(missing_indexes):
            _append_issue(
                issues,
                "required_values_missing",
                name,
                missing_indexes,
                row_count,
                f"{len(missing_indexes)} rows are missing a required value in '{name}'.",
                {"row_numbers": _row_numbers(missing_indexes), "required": True},
            )

        valid_mask, parsed = _typed_values(non_missing, constraint["type"])
        invalid_type_indexes = non_missing.index[~valid_mask]
        if len(invalid_type_indexes):
            _append_issue(
                issues,
                "schema_type_mismatch",
                name,
                invalid_type_indexes,
                len(non_missing),
                f"{len(invalid_type_indexes)} non-missing values in '{name}' do not match the expected {constraint['type']} type.",
                {
                    "row_numbers": _row_numbers(invalid_type_indexes),
                    "expected_type": constraint["type"],
                },
            )

        if parsed is not None and constraint["type"] in {"integer", "number"}:
            valid_numeric = parsed.loc[valid_mask]
            minimum = constraint.get("minimum")
            maximum = constraint.get("maximum")
            outside = pd.Series(False, index=valid_numeric.index, dtype=bool)
            if minimum is not None:
                outside |= valid_numeric < minimum
            if maximum is not None:
                outside |= valid_numeric > maximum
            outside_indexes = valid_numeric.index[outside]
            if len(outside_indexes):
                _append_issue(
                    issues,
                    "domain_out_of_range",
                    name,
                    outside_indexes,
                    len(non_missing),
                    f"{len(outside_indexes)} values in '{name}' fall outside the configured inclusive range.",
                    {
                        "row_numbers": _row_numbers(outside_indexes),
                        "minimum": minimum,
                        "maximum": maximum,
                        "bounds": "inclusive",
                    },
                )

        allowed_values = constraint.get("allowed_values")
        if allowed_values is not None:
            if constraint.get("case_sensitive", True):
                candidates = non_missing
                allowed = set(allowed_values)
            else:
                candidates = non_missing.str.casefold()
                allowed = {value.casefold() for value in allowed_values}
            invalid_domain_indexes = candidates.index[~candidates.isin(allowed)]
            if len(invalid_domain_indexes):
                _append_issue(
                    issues,
                    "domain_value_invalid",
                    name,
                    invalid_domain_indexes,
                    len(non_missing),
                    f"{len(invalid_domain_indexes)} values in '{name}' are not in the configured allowed-value set.",
                    {
                        "row_numbers": _row_numbers(invalid_domain_indexes),
                        "allowed_values": allowed_values,
                        "case_sensitive": constraint.get("case_sensitive", True),
                    },
                )

    unexpected_columns = [name for name in actual_columns if name not in expected_columns]
    if not allow_extra_columns:
        for name in unexpected_columns:
            issues.append(
                _issue(
                    "unexpected_schema_column",
                    "column",
                    name,
                    1,
                    1,
                    f"Column '{name}' is not declared in the expected schema.",
                    {"allow_extra_columns": False},
                )
            )

    severity_counts = {
        level: sum(issue["severity"] == level for issue in issues)
        for level in ("high", "medium", "low")
    }
    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "schema_validation_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shape": {"rows": int(row_count), "columns": int(column_count)},
        "schema_validation": {
            "passed": len(issues) == 0,
            "expected_column_count": len(expected_names),
            "present_column_count": present_count,
            "unexpected_columns": unexpected_columns,
            "allow_extra_columns": allow_extra_columns,
        },
        "issue_count": len(issues),
        "issues_by_severity": severity_counts,
        "issues": issues,
        "method_notes": [
            "Validation uses the caller-supplied schema; no business rules or ranges are inferred.",
            "Integer values must be finite whole numbers; number values must be finite.",
            "Boolean values accept true, false, 1, 0, yes, and no, ignoring surrounding whitespace and case.",
            "Configured numeric minimum and maximum bounds are inclusive.",
            "Allowed values are exact by default; case-insensitive matching is opt-in and does not trim whitespace.",
            "Required-value checks use pandas CSV missing-value parsing defaults.",
            "Schema validation is supplemental to the inference-based DQS and does not alter its component scores.",
            "The original uploaded CSV is preserved; validation does not clean, normalize, or delete values.",
        ],
    }
