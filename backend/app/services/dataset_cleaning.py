"""Preview and explicitly apply conservative CSV cleaning into immutable versions."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Dataset, DatasetVersion
from . import dataset_ingestion

VERSIONS_DIR = dataset_ingestion.BACKEND_DIR / "versions"
PREVIEW_ROW_LIMIT = 10
PREVIEW_CELL_LIMIT = 10


class DatasetCleaningRequestError(ValueError):
    """Raised when a requested cleaning operation cannot be applied safely."""


class DatasetCleaningFileUnavailableError(RuntimeError):
    """Raised when the selected source or derived file is missing or unsafe."""


class DatasetCleaningNoChangesError(RuntimeError):
    """Raised when a valid preview contains no changes to persist."""


def _load_base(
    dataset: Dataset, db: Session, base_version_id: int | None
) -> tuple[pd.DataFrame, DatasetVersion | None, str]:
    if base_version_id is None:
        path_value = dataset.original_path
        root = dataset_ingestion.UPLOAD_DIR
        encoding = dataset.encoding
        source_hash = dataset.sha256_hash or ""
        version = None
    else:
        version = db.get(DatasetVersion, base_version_id)
        if version is None or version.dataset_id != dataset.id:
            raise DatasetCleaningRequestError(
                "The selected base version does not belong to this dataset."
            )
        path_value = version.storage_path
        root = VERSIONS_DIR
        encoding = "utf-8"
        source_hash = version.sha256_hash

    try:
        root_path = root.resolve()
        source_path = Path(path_value).resolve(strict=True)
        source_path.relative_to(root_path)
    except (OSError, ValueError) as exc:
        raise DatasetCleaningFileUnavailableError(
            "The selected dataset version is missing or outside its permitted storage directory."
        ) from exc

    try:
        frame = pd.read_csv(source_path, encoding=encoding, dtype=str)
    except (OSError, UnicodeDecodeError, EmptyDataError, ParserError, ValueError) as exc:
        raise DatasetCleaningFileUnavailableError(
            "The selected CSV could not be read for cleaning."
        ) from exc
    return frame, version, source_hash


def _validate_columns(frame: pd.DataFrame, request: dict[str, Any]) -> None:
    selected = (
        request["fill_numeric_median"]
        + request["fill_categorical_mode"]
        + request["trim_whitespace"]
        + request["lowercase_categories"]
    )
    missing = sorted(set(selected) - set(map(str, frame.columns)))
    if missing:
        raise DatasetCleaningRequestError(
            "Unknown cleaning column(s): " + ", ".join(missing)
        )


def _display(value: Any) -> str | None:
    if pd.isna(value):
        return None
    return str(value)


def _build_preview(
    before: pd.DataFrame,
    after: pd.DataFrame,
    operation_summary: list[dict[str, Any]],
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    changed_row_count = 0
    removed_rows = set(before.index) - set(after.index)
    operations_by_column: dict[str, list[str]] = {}
    for item in operation_summary:
        for column in item.get("columns", []):
            operations_by_column.setdefault(column, []).append(item["operation"])

    for index, old_row in before.iterrows():
        if index in removed_rows:
            changed_row_count += 1
            if len(changes) < PREVIEW_ROW_LIMIT:
                changes.append({
                    "row_number": int(index) + 1,
                    "removed": True,
                    "changes": [{
                        "column": "*",
                        "before": "duplicate row",
                        "after": None,
                        "operations": ["drop_exact_duplicates"],
                    }],
                })
            continue

        new_row = after.loc[index]
        cell_changes = []
        for column in before.columns:
            old_value = old_row[column]
            new_value = new_row[column]
            old_missing = pd.isna(old_value)
            new_missing = pd.isna(new_value)
            if old_missing and new_missing:
                continue
            if not old_missing and not new_missing and str(old_value) == str(new_value):
                continue
            cell_changes.append({
                "column": str(column),
                "before": _display(old_value),
                "after": _display(new_value),
                "operations": operations_by_column.get(str(column), ["clean_value"]),
            })
            if len(cell_changes) >= PREVIEW_CELL_LIMIT:
                break
        if cell_changes:
            changed_row_count += 1
            if len(changes) < PREVIEW_ROW_LIMIT:
                changes.append({
                    "row_number": int(index) + 1,
                    "removed": False,
                    "changes": cell_changes,
                })

    return {
        "changed_row_count": changed_row_count,
        "removed_row_count": len(removed_rows),
        "sample_rows": changes,
        "sample_truncated": changed_row_count > len(changes),
        "operations": operation_summary,
    }


def _transform(
    frame: pd.DataFrame, request: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    _validate_columns(frame, request)
    result = frame.copy(deep=True)
    summary: list[dict[str, Any]] = []

    for column in request["trim_whitespace"]:
        original = result[column].copy()
        trimmed = original.astype("string").str.strip()
        changed = int(((original.astype("string") != trimmed) & original.notna()).sum())
        result[column] = trimmed.astype(object).where(trimmed.notna(), np.nan)
        summary.append({
            "operation": "trim_whitespace",
            "columns": [column],
            "affected_cells": changed,
        })

    for column in request["lowercase_categories"]:
        original = result[column].copy()
        lowered = original.astype("string").str.lower()
        changed = int(((original.astype("string") != lowered) & original.notna()).sum())
        result[column] = lowered.astype(object).where(lowered.notna(), np.nan)
        summary.append({
            "operation": "lowercase_categories",
            "columns": [column],
            "affected_cells": changed,
            "review_required": True,
        })

    for column in request["fill_numeric_median"]:
        non_missing = result[column].dropna()
        if non_missing.empty:
            raise DatasetCleaningRequestError(
                f"Cannot calculate a median for '{column}' because it has no observed values."
            )
        numeric = pd.to_numeric(non_missing, errors="coerce")
        finite = np.isfinite(numeric.to_numpy(dtype=float))
        if numeric.isna().any() or not finite.all():
            raise DatasetCleaningRequestError(
                f"'{column}' contains non-numeric or non-finite values; median imputation was not applied."
            )
        median = float(numeric.median())
        if not np.isfinite(median):
            raise DatasetCleaningRequestError(f"'{column}' has no finite median.")
        missing_count = int(result[column].isna().sum())
        result[column] = result[column].fillna(format(median, ".15g"))
        summary.append({
            "operation": "fill_numeric_median",
            "columns": [column],
            "affected_cells": missing_count,
            "imputation_value": format(median, ".15g"),
        })

    for column in request["fill_categorical_mode"]:
        non_missing = result[column].dropna().astype(str)
        if non_missing.empty:
            raise DatasetCleaningRequestError(
                f"Cannot calculate a mode for '{column}' because it has no observed values."
            )
        modes = non_missing.mode()
        mode_value = str(modes.iloc[0])
        missing_count = int(result[column].isna().sum())
        result[column] = result[column].fillna(mode_value)
        summary.append({
            "operation": "fill_categorical_mode",
            "columns": [column],
            "affected_cells": missing_count,
            "imputation_value": mode_value,
            "tie_break": "pandas mode ordering; first mode selected",
        })

    if request["drop_exact_duplicates"]:
        duplicate_count = int(result.duplicated(keep="first").sum())
        result = result.drop_duplicates(keep="first")
        summary.append({
            "operation": "drop_exact_duplicates",
            "columns": [],
            "affected_rows": duplicate_count,
            "comparison": "exact across all columns; first occurrence retained",
        })

    preview = _build_preview(frame, result, summary)
    return result, {
        "changed": preview["changed_row_count"] > 0,
        "preview": preview,
        "rows_before": int(frame.shape[0]),
        "rows_after": int(result.shape[0]),
        "columns": int(result.shape[1]),
    }


def _request_payload(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_version_id": request.get("base_version_id"),
        "drop_exact_duplicates": bool(request["drop_exact_duplicates"]),
        "fill_numeric_median": list(request["fill_numeric_median"]),
        "fill_categorical_mode": list(request["fill_categorical_mode"]),
        "trim_whitespace": list(request["trim_whitespace"]),
        "lowercase_categories": list(request["lowercase_categories"]),
    }


def get_cleaning_recommendations(
    dataset: Dataset, db: Session, base_version_id: int | None = None
) -> dict[str, Any]:
    """Suggest reviewable operations; never execute a recommendation."""
    frame, base_version, source_hash = _load_base(dataset, db, base_version_id)
    numeric_median: list[str] = []
    categorical_mode: list[str] = []
    trim_columns: list[str] = []
    lowercase_columns: list[str] = []

    for column in frame.columns:
        series = frame[column]
        missing_count = int(series.isna().sum())
        non_missing = series.dropna().astype(str)
        parsed = pd.to_numeric(non_missing, errors="coerce")
        finite_count = int(
            (parsed.notna() & np.isfinite(parsed.to_numpy(dtype=float))).sum()
        )
        numeric_like = (
            len(non_missing) >= 2 and finite_count / len(non_missing) >= 0.8
        )
        if missing_count and numeric_like:
            numeric_median.append(str(column))
        elif missing_count and not non_missing.empty:
            categorical_mode.append(str(column))

        if not non_missing.empty and bool(
            (non_missing != non_missing.str.strip()).any()
        ):
            trim_columns.append(str(column))

        trimmed = non_missing.str.strip()
        normalized = trimmed.str.casefold()
        if normalized.nunique() < trimmed.nunique():
            lowercase_columns.append(str(column))

    duplicate_count = int(frame.duplicated(keep="first").sum())
    recommendations = []
    if duplicate_count:
        recommendations.append({
            "operation": "drop_exact_duplicates",
            "recommended": True,
            "affected_count": duplicate_count,
            "risk": "low",
            "reason": "Exact repeated rows were found; the first occurrence can be retained.",
        })
    for column in numeric_median:
        recommendations.append({
            "operation": "fill_numeric_median",
            "column": column,
            "recommended": True,
            "affected_count": int(frame[column].isna().sum()),
            "risk": "medium",
            "reason": "The column is numeric-like and has missing values; median imputation changes the empirical distribution.",
        })
    for column in categorical_mode:
        recommendations.append({
            "operation": "fill_categorical_mode",
            "column": column,
            "recommended": True,
            "affected_count": int(frame[column].isna().sum()),
            "risk": "medium",
            "reason": "A non-missing mode exists; mode imputation can increase the apparent frequency of one category.",
        })
    for column in trim_columns:
        count = int(
            (
                frame[column].dropna().astype(str)
                != frame[column].dropna().astype(str).str.strip()
            ).sum()
        )
        recommendations.append({
            "operation": "trim_whitespace",
            "column": column,
            "recommended": True,
            "affected_count": count,
            "risk": "low",
            "reason": "Leading or trailing whitespace was detected; trimming preserves the remaining text.",
        })
    for column in lowercase_columns:
        count = int(
            (
                frame[column].dropna().astype(str)
                != frame[column].dropna().astype(str).str.lower()
            ).sum()
        )
        recommendations.append({
            "operation": "lowercase_categories",
            "column": column,
            "recommended": False,
            "affected_count": count,
            "risk": "high",
            "reason": "Case-only variants exist, but case may be meaningful; inspect values before explicitly requesting lower-case normalization.",
        })

    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "base_version_id": base_version.id if base_version else None,
        "source_sha256": source_hash,
        "shape": {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])},
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "method_notes": [
            "Recommendations are advisory and never execute automatically.",
            "Median and mode imputation can change distributions and must be justified for the dataset.",
            "Case normalization is not recommended by default because capitalization can carry meaning.",
            "A preview must be reviewed before an explicit apply request creates an immutable version.",
        ],
    }


def preview_cleaning(
    dataset: Dataset, request: dict[str, Any], db: Session
) -> dict[str, Any]:
    """Return a bounded before/after preview without writing files or database rows."""
    frame, base_version, source_hash = _load_base(
        dataset, db, request.get("base_version_id")
    )
    _, outcome = _transform(frame, request)
    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "base_version_id": base_version.id if base_version else None,
        "source_sha256": source_hash,
        "previewed_at": datetime.now(timezone.utc).isoformat(),
        **outcome,
        "method_notes": [
            "Preview is read-only; no file or database version is created.",
            "Row numbers refer to the selected base file and are one-based.",
            "At most ten changed rows and ten changed cells per row are returned.",
            "Case normalization is explicit and may collapse semantically distinct categories.",
        ],
    }


def list_dataset_versions(dataset_id: int, db: Session) -> list[dict[str, Any]]:
    """List immutable derived versions without exposing server storage paths."""
    versions = db.scalars(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.asc())
    ).all()
    return [
        {
            "id": version.id,
            "dataset_id": version.dataset_id,
            "parent_version_id": version.parent_version_id,
            "version_number": version.version_number,
            "filename": version.filename,
            "rows_count": version.rows_count,
            "columns_count": version.columns_count,
            "file_size_bytes": version.file_size_bytes,
            "sha256_hash": version.sha256_hash,
            "operations": json.loads(version.operations_json),
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
        for version in versions
    ]


def apply_cleaning(
    dataset: Dataset, request: dict[str, Any], db: Session
) -> dict[str, Any]:
    """Apply only the supplied operations and persist a new immutable CSV version."""
    frame, base_version, source_hash = _load_base(
        dataset, db, request.get("base_version_id")
    )
    cleaned, outcome = _transform(frame, request)
    if not outcome["changed"]:
        raise DatasetCleaningNoChangesError(
            "The selected operations produced no changes; no dataset version was created."
        )

    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    output = cleaned.to_csv(index=False, lineterminator="\n").encode("utf-8")
    storage_path = VERSIONS_DIR / f"{uuid.uuid4().hex}.csv"
    try:
        with storage_path.open("xb") as handle:
            handle.write(output)
    except OSError as exc:
        raise DatasetCleaningFileUnavailableError(
            "The cleaned version could not be written to version storage."
        ) from exc

    version_number = (
        db.scalar(
            select(func.max(DatasetVersion.version_number)).where(
                DatasetVersion.dataset_id == dataset.id
            )
        )
        or 0
    ) + 1
    result_hash = hashlib.sha256(output).hexdigest()
    manifest = {
        "request": _request_payload(request),
        "summary": outcome["preview"]["operations"],
        "base_sha256": source_hash,
        "result_sha256": result_hash,
    }
    version = DatasetVersion(
        dataset_id=dataset.id,
        parent_version_id=base_version.id if base_version else None,
        version_number=version_number,
        filename=dataset.filename,
        storage_path=str(storage_path),
        rows_count=int(cleaned.shape[0]),
        columns_count=int(cleaned.shape[1]),
        file_size_bytes=len(output),
        sha256_hash=result_hash,
        operations_json=json.dumps(manifest, sort_keys=True, ensure_ascii=False),
    )
    try:
        db.add(version)
        db.commit()
        db.refresh(version)
    except IntegrityError as exc:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise DatasetCleaningRequestError(
            "A concurrent version was created; refresh the version list and retry."
        ) from exc
    except Exception:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise

    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "rows_count": version.rows_count,
            "columns_count": version.columns_count,
            "file_size_bytes": version.file_size_bytes,
            "sha256_hash": version.sha256_hash,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        },
        "base_sha256": source_hash,
        "preview": outcome["preview"],
        "source_preserved": True,
        "method_notes": [
            "The source dataset and all prior versions are retained unchanged.",
            "Each successful apply writes a new generated CSV and a new version record.",
            "Version numbering is unique per source dataset; parent_version_id records the selected base.",
        ],
    }
