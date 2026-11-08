"""Compare original and immutable derived dataset quality without mutation."""
from datetime import datetime, timezone
from typing import Any

from ..models import Dataset, DatasetVersion
from . import dataset_cleaning
from .dataset_quality import (
    DatasetQualityFileUnavailableError,
    assess_dataset_quality,
)

_COMPONENTS = ("completeness", "validity", "uniqueness", "consistency")
_SEVERITIES = ("high", "medium", "low")


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


def compare_dataset_version_quality(
    dataset: Dataset, version: DatasetVersion
) -> dict[str, Any]:
    """Recalculate the same DQS for the original and one verified derived version."""
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

    component_deltas: dict[str, dict[str, Any]] = {}
    for name in _COMPONENTS:
        left = before["components"][name]
        right = after["components"][name]
        comparable = (
            left["applicable"]
            and right["applicable"]
            and left["score"] is not None
            and right["score"] is not None
        )
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
        "method_notes": [
            "Both snapshots are recalculated with the same inference-based DQS rules and nominal component weights.",
            "A positive overall or component delta means a higher score under this DQS definition; it is not proof of improved downstream model performance.",
            "A component delta is null when either version has no assessable denominator for that component.",
            "If component applicability changes, the overall score uses a different active-weight denominator; interpret the delta with that change in mind.",
            "Issue counts are counts of findings, not counts of defective cells or rows; compare component denominators and evidence before drawing conclusions.",
            "The original upload and derived version are read-only during comparison.",
        ],
    }


__all__ = ["compare_dataset_version_quality", "DatasetQualityFileUnavailableError"]
