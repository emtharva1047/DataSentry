"""Compare quality and numeric profiles for original and immutable derived datasets."""
from datetime import datetime, timezone
from typing import Any

from ..models import Dataset, DatasetVersion
from . import dataset_cleaning
from .dataset_profiling import DatasetFileUnavailableError, profile_dataset
from .dataset_quality import (
    DatasetQualityFileUnavailableError,
    assess_dataset_quality,
)

_COMPONENTS = ("completeness", "validity", "uniqueness", "consistency")
_SEVERITIES = ("high", "medium", "low")
_NUMERIC_SUMMARY_FIELDS = ("min", "max", "mean", "median", "std", "q1", "q3")
MAX_PROFILE_COMPARISON_COLUMNS = 20


def _snapshot(report: dict[str, Any], version: DatasetVersion | None) -> dict[str, Any]:
    score = report["data_quality_score"]
    return {
        "source_version_id": version.id if version else None,
        "version_number": version.version_number if version else None,
        "source_sha256": report["source_sha256"],
        "shape": report["shape"],
        "overall": score["overall"],
        "active_weight_total": score["active_weight_total"],
        "components": score["components"],
        "issue_count": report["issue_count"],
        "issues_by_severity": report["issues_by_severity"],
    }


def _numeric_columns(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: item
        for item in profile["columns"]
        if item["inferred_type"] in {"integer", "number"}
    }


def _shared_histogram_ranges(before: dict[str, Any], after: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Use shared min/max ranges so before/after histogram bins align."""
    left = _numeric_columns(before)
    right = _numeric_columns(after)
    ranges: dict[str, tuple[float, float]] = {}
    for name in left.keys() & right.keys():
        left_summary = left[name].get("numeric_summary")
        right_summary = right[name].get("numeric_summary")
        if not left_summary or not right_summary:
            continue
        values = (
            left_summary.get("min"),
            left_summary.get("max"),
            right_summary.get("min"),
            right_summary.get("max"),
        )
        if any(value is None for value in values):
            continue
        ranges[name] = (
            min(float(values[0]), float(values[2])),
            max(float(values[1]), float(values[3])),
        )
    return ranges


def _correlation_map(profile: dict[str, Any]) -> tuple[dict[tuple[str, str], float | None], int]:
    correlation = profile.get("correlations")
    if not correlation:
        return {}, 0
    names = correlation["columns"]
    matrix = correlation["matrix"]
    values: dict[tuple[str, str], float | None] = {}
    for left_index, left_name in enumerate(names):
        for right_index in range(left_index + 1, len(names)):
            right_name = names[right_index]
            values[tuple(sorted((left_name, right_name)))] = matrix[left_index][right_index]
    return values, len(names)


def _profile_comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    left_columns = _numeric_columns(before)
    right_columns = _numeric_columns(after)
    all_names = list(dict.fromkeys([*left_columns, *right_columns]))
    selected_names = all_names[:MAX_PROFILE_COMPARISON_COLUMNS]
    numeric_results: list[dict[str, Any]] = []

    for name in selected_names:
        left = left_columns.get(name)
        right = right_columns.get(name)
        left_summary = left.get("numeric_summary") if left else None
        right_summary = right.get("numeric_summary") if right else None
        comparable = left_summary is not None and right_summary is not None
        deltas = {
            field: (
                round(float(right_summary[field]) - float(left_summary[field]), 4)
                if comparable and left_summary.get(field) is not None and right_summary.get(field) is not None
                else None
            )
            for field in _NUMERIC_SUMMARY_FIELDS
        }
        left_histogram = left.get("histogram", []) if left else []
        right_histogram = right.get("histogram", []) if right else []
        shared_bins = (
            comparable
            and len(left_histogram) == len(right_histogram)
            and all(
                left_bin["bin_start"] == right_bin["bin_start"]
                and left_bin["bin_end"] == right_bin["bin_end"]
                for left_bin, right_bin in zip(left_histogram, right_histogram)
            )
        )
        numeric_results.append({
            "column": name,
            "status": "comparable" if comparable else "not_comparable",
            "before_summary": left_summary,
            "after_summary": right_summary,
            "summary_deltas": deltas,
            "before_histogram": left_histogram,
            "after_histogram": right_histogram,
            "histogram_bins_comparable": bool(shared_bins),
        })

    before_correlations, before_correlation_columns = _correlation_map(before)
    after_correlations, after_correlation_columns = _correlation_map(after)
    all_pairs = set(before_correlations) | set(after_correlations)
    comparable_pairs: list[dict[str, Any]] = []
    skipped_pairs = 0
    for left_name, right_name in sorted(all_pairs):
        left_value = before_correlations.get((left_name, right_name))
        right_value = after_correlations.get((left_name, right_name))
        if left_value is None or right_value is None:
            skipped_pairs += 1
            continue
        comparable_pairs.append({
            "left_column": left_name,
            "right_column": right_name,
            "before": left_value,
            "after": right_value,
            "delta": round(float(right_value) - float(left_value), 4),
        })

    return {
        "numeric_column_count_before": len(left_columns),
        "numeric_column_count_after": len(right_columns),
        "numeric_columns_truncated": len(all_names) > MAX_PROFILE_COMPARISON_COLUMNS,
        "numeric_columns": numeric_results,
        "correlations": {
            "method": "pearson",
            "before_column_count": before_correlation_columns,
            "after_column_count": after_correlation_columns,
            "comparable_pair_count": len(comparable_pairs),
            "skipped_pair_count": skipped_pairs,
            "pairs": comparable_pairs,
        },
        "method_notes": [
            "Numeric summary deltas are calculated as after minus before.",
            "Before/after histograms use common bin edges for columns numeric in both versions; counts can therefore be compared directly for those columns.",
            "Pearson correlation deltas are calculated only for column pairs with a defined correlation in both versions.",
            "Only the first 20 numeric columns are included to bound response size; categorical frequency comparisons are not included.",
        ],
    }


def compare_dataset_version_quality(dataset: Dataset, version: DatasetVersion) -> dict[str, Any]:
    """Recalculate DQS and numeric profiles for the original and one derived version."""
    before_report = assess_dataset_quality(dataset)
    after_report = assess_dataset_quality(
        dataset,
        source_path=version.storage_path,
        allowed_root=dataset_cleaning.VERSIONS_DIR,
        encoding="utf-8",
        source_version_id=version.id,
        source_sha256=version.sha256_hash,
    )
    before = _snapshot(before_report, None)
    after = _snapshot(after_report, version)

    before_initial = profile_dataset(dataset)
    after_initial = profile_dataset(
        dataset,
        source_path=version.storage_path,
        allowed_root=dataset_cleaning.VERSIONS_DIR,
        encoding="utf-8",
        source_version_id=version.id,
        source_sha256=version.sha256_hash,
    )
    shared_ranges = _shared_histogram_ranges(before_initial, after_initial)
    if shared_ranges:
        before_profile = profile_dataset(dataset, histogram_ranges=shared_ranges)
        after_profile = profile_dataset(
            dataset,
            source_path=version.storage_path,
            allowed_root=dataset_cleaning.VERSIONS_DIR,
            encoding="utf-8",
            histogram_ranges=shared_ranges,
            source_version_id=version.id,
            source_sha256=version.sha256_hash,
        )
    else:
        before_profile = before_initial
        after_profile = after_initial

    component_deltas: dict[str, dict[str, Any]] = {}
    for name in _COMPONENTS:
        left = before["components"][name]
        right = after["components"][name]
        comparable = left["applicable"] and right["applicable"] and left["score"] is not None and right["score"] is not None
        component_deltas[name] = {
            "score_delta": round(right["score"] - left["score"], 2) if comparable else None,
            "numerator_delta": right["numerator"] - left["numerator"],
            "denominator_delta": right["denominator"] - left["denominator"],
            "applicable_before": left["applicable"],
            "applicable_after": right["applicable"],
        }

    overall_comparable = before["overall"] is not None and after["overall"] is not None
    overall_delta = round(after["overall"] - before["overall"], 2) if overall_comparable else None
    severity_deltas = {
        level: after["issues_by_severity"][level] - before["issues_by_severity"][level]
        for level in _SEVERITIES
    }

    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "before": before,
        "after": after,
        "delta": {
            "overall": overall_delta,
            "rows": after["shape"]["rows"] - before["shape"]["rows"],
            "columns": after["shape"]["columns"] - before["shape"]["columns"],
            "issue_count": after["issue_count"] - before["issue_count"],
            "issues_by_severity": severity_deltas,
            "components": component_deltas,
        },
        "profile_comparison": _profile_comparison(before_profile, after_profile),
        "method_notes": [
            "Both snapshots are recalculated with the same inference-based DQS rules and nominal component weights.",
            "A positive overall or component delta means a higher score under this DQS definition; it is not proof of improved downstream model performance.",
            "A component delta is null when either version has no assessable denominator for that component.",
            "If component applicability changes, the overall score uses a different active-weight denominator; interpret the delta with that change in mind.",
            "Issue counts are counts of findings, not counts of defective cells or rows; compare component denominators and evidence before drawing conclusions.",
            "The original upload and derived version are read-only during comparison.",
            "Numeric profile comparisons include summary deltas, aligned histograms, and pairwise Pearson correlation deltas for up to 20 numeric columns.",
        ],
    }


__all__ = [
    "compare_dataset_version_quality",
    "DatasetQualityFileUnavailableError",
    "DatasetFileUnavailableError",
]
