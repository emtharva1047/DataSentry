"""UCI Bike Sharing mixed-type detector reference and benchmark runner."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .dataset_benchmark import (
    DEFAULT_BENCHMARK_RATES,
    DEFAULT_BENCHMARK_SEEDS,
    run_synthetic_detector_benchmark,
)
from .dataset_bike_reference_experiment import (
    CATEGORICAL_COLUMNS,
    build_bike_sharing_reference,
)

# The source stores these predictors as integer codes. Convert them to explicit
# semantic labels before detector benchmarking so numeric-looking categories
# cannot be misclassified as continuous measurements.
CATEGORY_LABELS: dict[str, dict[int, str]] = {
    "season": {
        1: "season_spring",
        2: "season_summer",
        3: "season_fall",
        4: "season_winter",
    },
    "yr": {0: "year_2011", 1: "year_2012"},
    "mnth": {
        1: "month_january",
        2: "month_february",
        3: "month_march",
        4: "month_april",
        5: "month_may",
        6: "month_june",
        7: "month_july",
        8: "month_august",
        9: "month_september",
        10: "month_october",
        11: "month_november",
        12: "month_december",
    },
    "hr": {value: f"hour_{value:02d}" for value in range(24)},
    "holiday": {0: "not_holiday", 1: "holiday"},
    "weekday": {
        0: "weekday_sunday",
        1: "weekday_monday",
        2: "weekday_tuesday",
        3: "weekday_wednesday",
        4: "weekday_thursday",
        5: "weekday_friday",
        6: "weekday_saturday",
    },
    "workingday": {0: "non_working_day", 1: "working_day"},
    "weathersit": {
        1: "weather_clear",
        2: "weather_mist_cloudy",
        3: "weather_light_rain_snow",
        4: "weather_heavy_rain_snow",
    },
}


def _frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\\n").encode("utf-8")
    return sha256(payload).hexdigest()


def _semantic_category(series: pd.Series, column: str) -> pd.Series:
    """Map a validated integer-coded source column to readable category labels."""
    codes = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    if (
        not np.isfinite(codes).all()
        or not np.equal(codes, np.floor(codes)).all()
    ):
        raise ValueError(f"{column} must contain finite integer category codes")
    mapping = CATEGORY_LABELS[column]
    unknown = sorted({int(value) for value in codes} - set(mapping))
    if unknown:
        raise ValueError(
            f"{column} contains unsupported category code(s): "
            + ", ".join(str(value) for value in unknown)
        )
    return pd.Series(
        [mapping[int(value)] for value in codes],
        index=series.index,
        name=column,
        dtype="string",
    )


def build_bike_sharing_detector_reference() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build a detector frame with semantic categories and continuous measures.

    The regression target is intentionally excluded. The eight integer-coded
    categorical predictors are mapped to labels so the shared corruption
    generator and detector preflight infer the correct feature semantics.
    """
    features, _, metadata = build_bike_sharing_reference()
    detector_frame = features.copy(deep=True)
    for column in CATEGORICAL_COLUMNS:
        detector_frame[column] = _semantic_category(
            detector_frame[column], column
        )

    if detector_frame.isna().any().any() or detector_frame.duplicated().any():
        raise ValueError(
            "the Bike Sharing detector reference must be complete and row-unique"
        )

    numeric_columns = [
        name for name in detector_frame.columns
        if name not in CATEGORICAL_COLUMNS
    ]
    if len(numeric_columns) != 5:
        raise ValueError("the Bike Sharing detector reference must have five numeric features")

    detector_metadata = {
        **metadata,
        "detector_frame_sha256": _frame_sha256(detector_frame),
        "detector_frame_shape": {
            "rows": int(detector_frame.shape[0]),
            "columns": int(detector_frame.shape[1]),
        },
        "detector_categorical_features": list(CATEGORICAL_COLUMNS),
        "detector_numeric_features": numeric_columns,
        "categorical_label_maps": {
            column: {str(code): label for code, label in mapping.items()}
            for column, mapping in CATEGORY_LABELS.items()
        },
        "target_excluded": True,
        "semantic_mapping_note": (
            "Integer-coded calendar/weather predictors are mapped to explicit "
            "semantic string labels before corruption and detector evaluation. "
            "The cnt target and direct target components are not included."
        ),
    }
    return detector_frame, detector_metadata


def run_bike_sharing_detector_benchmark(
    *,
    rates: Sequence[float] = DEFAULT_BENCHMARK_RATES,
    seeds: Sequence[int] = DEFAULT_BENCHMARK_SEEDS,
    defects: Sequence[str] | None = None,
    n_estimators: int = 100,
    contamination: float = 0.05,
    iqr_multiplier: float = 1.5,
    robust_z_threshold: float = 3.5,
) -> dict[str, Any]:
    """Benchmark applicable production detectors on the mixed-type UCI reference."""
    frame, metadata = build_bike_sharing_detector_reference()
    benchmark = run_synthetic_detector_benchmark(
        frame,
        rates=rates,
        seeds=seeds,
        defects=defects,
        n_estimators=n_estimators,
        contamination=contamination,
        iqr_multiplier=iqr_multiplier,
        robust_z_threshold=robust_z_threshold,
    )
    complete = all(
        experiment["status"] == "completed"
        for experiment in benchmark["experiments"]
    )
    return {
        "schema_version": 1,
        "experiment": "uci_bike_sharing_synthetic_detector_benchmark",
        "dataset": metadata,
        "benchmark": benchmark,
        "status": "completed" if complete else "incomplete",
        "scope_limitations": [
            "The reference is one public hourly dataset; results are not universal detector estimates.",
            "Integer-coded categorical fields are mapped to documented semantic labels before corruption.",
            "Cell-level and row-level metrics follow the defect-specific evaluation unit in the shared benchmark runner.",
            "The categorical rule can flag legitimate case variants and is evaluated against injected-only labels.",
            "Statistical outliers in the clean reference are retained and count as false positives when flagged.",
            "Python tracemalloc is a partial allocation proxy and does not capture every native allocation.",
        ],
    }
