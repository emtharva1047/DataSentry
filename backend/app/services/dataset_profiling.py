"""Read-only dataset profiling for uploaded CSV files."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.api import types as ptypes
from pandas.errors import EmptyDataError, ParserError

from ..models import Dataset
from . import dataset_ingestion

MAX_CORRELATION_COLUMNS = 20
HISTOGRAM_BINS = 10
TOP_CATEGORY_LIMIT = 10


class DatasetFileUnavailableError(RuntimeError):
    """Raised when a dataset's stored source file is missing or unsafe to read."""


def _number_or_none(value: Any) -> float | None:
    """Convert a scalar to finite JSON-safe numeric output."""
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return round(number, 4) if np.isfinite(number) else None


def _column_type(series: pd.Series, unique_count: int, row_count: int) -> str:
    if ptypes.is_bool_dtype(series.dtype):
        return "boolean"
    if ptypes.is_integer_dtype(series.dtype):
        return "integer"
    if ptypes.is_numeric_dtype(series.dtype):
        numeric_values = pd.to_numeric(series, errors="coerce").dropna()
        if not numeric_values.empty and bool(np.equal(np.mod(numeric_values.to_numpy(), 1), 0).all()):
            return "integer"
        return "number"
    if ptypes.is_datetime64_any_dtype(series.dtype):
        return "datetime"
    if unique_count == 0:
        return "unknown"
    categorical_threshold = min(20, max(5, int(row_count * 0.1)))
    return "categorical" if unique_count <= categorical_threshold else "text"


def _profile_column(name: str, series: pd.Series, row_count: int, histogram_range: tuple[float, float] | None = None) -> dict[str, Any]:
    non_null = int(series.notna().sum())
    missing = row_count - non_null
    unique_count = int(series.nunique(dropna=True))
    kind = _column_type(series, unique_count, row_count)
    profile: dict[str, Any] = {
        "name": str(name),
        "inferred_type": kind,
        "non_null_count": non_null,
        "missing_count": missing,
        "missing_pct": round((missing / row_count) * 100, 2) if row_count else 0.0,
        "unique_count": unique_count,
        "sample_values": series.dropna().astype(str).drop_duplicates().head(5).tolist(),
    }

    if kind in {"integer", "number"}:
        values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
        if not values.empty:
            profile["numeric_summary"] = {
                "min": _number_or_none(values.min()),
                "max": _number_or_none(values.max()),
                "mean": _number_or_none(values.mean()),
                "median": _number_or_none(values.median()),
                "std": _number_or_none(values.std()),
                "q1": _number_or_none(values.quantile(0.25)),
                "q3": _number_or_none(values.quantile(0.75)),
            }
            histogram_kwargs: dict[str, Any] = {}
            if histogram_range is not None:
                lower, upper = histogram_range
                if lower == upper:
                    padding = max(abs(lower) * 0.01, 0.5)
                    lower -= padding
                    upper += padding
                histogram_kwargs["range"] = (lower, upper)
            counts, edges = np.histogram(values.to_numpy(), bins=HISTOGRAM_BINS, **histogram_kwargs)
            profile["histogram"] = [
                {
                    "bin_start": _number_or_none(edges[index]),
                    "bin_end": _number_or_none(edges[index + 1]),
                    "count": int(counts[index]),
                }
                for index in range(len(counts))
            ]
        else:
            profile["numeric_summary"] = None
            profile["histogram"] = []
    else:
        frequencies = series.dropna().astype(str).value_counts().head(TOP_CATEGORY_LIMIT)
        profile["top_values"] = [
            {"value": str(value), "count": int(count)}
            for value, count in frequencies.items()
        ]
        profile["other_count"] = max(0, non_null - int(frequencies.sum()))

    return profile


def profile_dataset(
    dataset: Dataset,
    *,
    source_path: str | Path | None = None,
    allowed_root: Path | None = None,
    encoding: str | None = None,
    histogram_ranges: dict[str, tuple[float, float]] | None = None,
    source_version_id: int | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Profile an upload or a derived CSV under an explicitly permitted root."""
    permitted_root = (allowed_root or dataset_ingestion.UPLOAD_DIR).resolve()
    candidate_path = source_path if source_path is not None else dataset.original_path
    try:
        resolved_path = Path(candidate_path).resolve(strict=True)
        resolved_path.relative_to(permitted_root)
    except (OSError, ValueError) as exc:
        raise DatasetFileUnavailableError(
            "The stored dataset file is unavailable or outside its permitted storage directory."
        ) from exc

    try:
        frame = pd.read_csv(resolved_path, encoding=encoding or dataset.encoding)
    except (OSError, UnicodeDecodeError, EmptyDataError, ParserError, ValueError) as exc:
        raise DatasetFileUnavailableError("The stored CSV could not be read for profiling.") from exc

    row_count, column_count = frame.shape
    ranges = histogram_ranges or {}
    columns = [
        _profile_column(str(name), frame[name], row_count, ranges.get(str(name)))
        for name in frame.columns
    ]
    missing_cells = int(frame.isna().sum().sum())
    numeric_names = [item["name"] for item in columns if item["inferred_type"] in {"integer", "number"}]
    categorical_names = [item["name"] for item in columns if item["inferred_type"] in {"boolean", "categorical", "text"}]

    correlation_names = numeric_names[:MAX_CORRELATION_COLUMNS]
    correlations: dict[str, Any] | None = None
    if len(correlation_names) >= 2:
        matrix = frame[correlation_names].corr(method="pearson")
        correlations = {
            "method": "pearson",
            "columns": correlation_names,
            "matrix": [
                [_number_or_none(value) for value in row]
                for row in matrix.to_numpy().tolist()
            ],
            "truncated": len(numeric_names) > MAX_CORRELATION_COLUMNS,
        }

    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "source_version_id": source_version_id,
        "source_sha256": source_sha256 if source_sha256 is not None else dataset.sha256_hash,
        "profile_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shape": {"rows": int(row_count), "columns": int(column_count)},
        "memory_usage_bytes": int(frame.memory_usage(index=True, deep=True).sum()),
        "missing_cells": missing_cells,
        "total_cells": int(row_count * column_count),
        "numeric_column_count": len(numeric_names),
        "categorical_column_count": len(categorical_names),
        "columns": columns,
        "correlations": correlations,
    }
