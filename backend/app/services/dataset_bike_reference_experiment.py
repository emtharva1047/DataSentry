"""UCI Bike Sharing mixed-type reference and downstream regression experiment."""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Sequence
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile
import numpy as np
import pandas as pd
import sklearn
from .dataset_regression_experiment import DEFAULT_REGRESSION_SEEDS, run_regression_corruption_experiment

BIKE_SHARING_SOURCE_URL = "https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset"
BIKE_SHARING_ARCHIVE_URL = "https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip"
BIKE_SHARING_DOI = "10.24432/C5W894"
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_HOUR_CSV_BYTES = 5 * 1024 * 1024
MINIMUM_REFERENCE_ROWS = 10_000
CATEGORICAL_COLUMNS = ("season", "yr", "mnth", "hr", "holiday", "weekday", "workingday", "weathersit")
NUMERIC_COLUMNS = ("temp", "atemp", "hum", "windspeed", "day_index")
TARGET_COLUMN = "cnt"
REQUIRED_COLUMNS = (
    "instant", "dteday", "season", "yr", "mnth", "hr", "holiday", "weekday",
    "workingday", "weathersit", "temp", "atemp", "hum", "windspeed",
    "casual", "registered", "cnt",
)


def _frame_sha256(frame: pd.DataFrame) -> str:
    return sha256(frame.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def _download_archive() -> bytes:
    request = Request(BIKE_SHARING_ARCHIVE_URL, headers={"User-Agent": "DataSentry-Research/1.0"})
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read(MAX_ARCHIVE_BYTES + 1)
    except OSError as exc:
        raise RuntimeError("the UCI Bike Sharing archive could not be downloaded") from exc
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("the UCI Bike Sharing archive exceeds the 10 MiB safety limit")
    if not payload:
        raise ValueError("the UCI Bike Sharing archive is empty")
    return payload


def _build_from_archive(
    archive_payload: bytes, *, minimum_rows: int = MINIMUM_REFERENCE_ROWS,
    retrieval_mode: str = "provided_archive",
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not isinstance(archive_payload, bytes) or not archive_payload:
        raise ValueError("archive_payload must be non-empty bytes")
    if isinstance(minimum_rows, bool) or not isinstance(minimum_rows, int) or minimum_rows < 30:
        raise ValueError("minimum_rows must be an integer of at least 30")
    if len(archive_payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("the UCI Bike Sharing archive exceeds the 10 MiB safety limit")
    if retrieval_mode not in {"provided_archive", "downloaded_archive"}:
        raise ValueError("retrieval_mode must be provided_archive or downloaded_archive")
    try:
        with ZipFile(BytesIO(archive_payload)) as archive:
            matches = [name for name in archive.namelist() if PurePosixPath(name).name.casefold() == "hour.csv"]
            if len(matches) != 1:
                raise ValueError("the archive must contain exactly one hour.csv file")
            info = archive.getinfo(matches[0])
            if info.file_size > MAX_HOUR_CSV_BYTES:
                raise ValueError("hour.csv exceeds the 5 MiB safety limit")
            csv_payload = archive.read(matches[0])
    except BadZipFile as exc:
        raise ValueError("the UCI Bike Sharing archive is not a valid ZIP file") from exc
    try:
        source = pd.read_csv(BytesIO(csv_payload), encoding="utf-8-sig")
    except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError, ValueError) as exc:
        raise ValueError("the UCI Bike Sharing hour.csv file could not be parsed") from exc
    missing = [name for name in REQUIRED_COLUMNS if name not in source.columns]
    if missing:
        raise ValueError("hour.csv is missing required columns: " + ", ".join(missing))
    if len(source) < minimum_rows:
        raise ValueError(f"hour.csv must contain at least {minimum_rows} rows")
    if source.loc[:, list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("the UCI reference contains missing values in required columns")

    instant = pd.to_numeric(source["instant"], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(instant).all() or len(np.unique(instant)) != len(instant):
        raise ValueError("instant must contain unique finite record identifiers")
    source = source.assign(_instant_numeric=instant).sort_values("_instant_numeric", kind="stable").reset_index(drop=True)
    if not np.all(np.diff(source["_instant_numeric"].to_numpy(dtype=float)) > 0):
        raise ValueError("instant must define a strictly increasing chronological order")
    dates = pd.to_datetime(source["dteday"], errors="coerce")
    if dates.isna().any():
        raise ValueError("dteday contains an invalid date")
    day_index = (dates - dates.min()).dt.days.astype(int)

    numeric_source = {}
    for name in ("temp", "atemp", "hum", "windspeed", "casual", "registered", "cnt"):
        values = pd.to_numeric(source[name], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{name} must contain only finite numeric values")
        numeric_source[name] = values
    if not np.array_equal(numeric_source["cnt"], numeric_source["casual"] + numeric_source["registered"]):
        raise ValueError("cnt must equal casual plus registered in the UCI source")

    features = pd.DataFrame(index=source.index)
    for name in CATEGORICAL_COLUMNS:
        values = pd.to_numeric(source[name], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ValueError(f"categorical code column {name} must contain finite integers")
        features[name] = values.astype(int).astype(str)
    for name in ("temp", "atemp", "hum", "windspeed"):
        features[name] = numeric_source[name].astype(float)
    features["day_index"] = day_index.to_numpy(dtype=int)
    target = pd.Series(numeric_source[TARGET_COLUMN], name=TARGET_COLUMN, dtype=float)
    full_frame = features.copy(deep=True)
    full_frame[TARGET_COLUMN] = target
    if full_frame.isna().any().any() or full_frame.duplicated().any():
        raise ValueError("the selected Bike Sharing analysis frame must be complete and row-unique")

    metadata = {
        "name": "Bike Sharing (hourly)",
        "repository": "UCI Machine Learning Repository",
        "uci_dataset_id": 275,
        "doi": BIKE_SHARING_DOI,
        "license": "CC BY 4.0",
        "source_url": BIKE_SHARING_SOURCE_URL,
        "archive_url": BIKE_SHARING_ARCHIVE_URL,
        "source_file": "hour.csv",
        "retrieval_mode": retrieval_mode,
        "archive_sha256": sha256(archive_payload).hexdigest(),
        "hour_csv_sha256": sha256(csv_payload).hexdigest(),
        "analysis_frame_sha256": _frame_sha256(full_frame),
        "rows": len(full_frame),
        "source_columns": len(REQUIRED_COLUMNS),
        "model_feature_count": len(features.columns),
        "target_column": TARGET_COLUMN,
        "target_definition": "total hourly rentals (cnt = casual + registered)",
        "excluded_columns": {
            "instant": "record identifier; used only to preserve chronological order",
            "dteday": "used only to derive day_index and preserve chronological order",
            "casual": "excluded because it is a direct component of cnt",
            "registered": "excluded because it is a direct component of cnt",
        },
        "categorical_features": list(CATEGORICAL_COLUMNS),
        "numeric_features": list(NUMERIC_COLUMNS),
        "derived_features": [{
            "name": "day_index", "source_column": "dteday",
            "method": "integer days since the earliest source date",
            "is_original_dataset_feature": False,
        }],
        "date_range": {"start": dates.min().date().isoformat(), "end": dates.max().date().isoformat()},
        "software_versions": {"pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "provenance_note": (
            "Rows are sorted by instant. instant and dteday are not predictors; casual and registered "
            "are excluded because they sum directly to cnt. day_index is a documented derived feature."
        ),
    }
    return features.reset_index(drop=True), full_frame.reset_index(drop=True), metadata


def build_bike_sharing_reference() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Download and validate the public UCI hourly Bike Sharing reference."""
    payload = _download_archive()
    return _build_from_archive(payload, minimum_rows=MINIMUM_REFERENCE_ROWS, retrieval_mode="downloaded_archive")


def run_bike_sharing_regression_experiment(
    *, rates: Sequence[float] = (0.01, 0.05, 0.10),
    seeds: Sequence[int] = DEFAULT_REGRESSION_SEEDS, test_size: float = 0.25, alpha: float = 1.0,
) -> dict[str, Any]:
    """Run multi-rate, multi-seed downstream regression on UCI Bike Sharing."""
    features, full_frame, metadata = build_bike_sharing_reference()
    normalized_rates = tuple(float(rate) for rate in rates)
    if not normalized_rates or len(set(normalized_rates)) != len(normalized_rates) or any(
        not np.isfinite(rate) or not 0 < rate <= 0.5 for rate in normalized_rates
    ):
        raise ValueError("rates must be distinct finite values in (0, 0.5]")
    experiments = [
        run_regression_corruption_experiment(
            full_frame, target_column=TARGET_COLUMN, feature_columns=list(features.columns),
            numeric_columns=NUMERIC_COLUMNS, categorical_columns=CATEGORICAL_COLUMNS,
            seeds=seeds, test_size=test_size, corruption_rate=rate, alpha=alpha,
        )
        for rate in normalized_rates
    ]
    return {
        "schema_version": 1,
        "dataset": metadata,
        "downstream_regression": {
            "corruption_type": "training_feature_missingness",
            "corruption_rates": list(normalized_rates),
            "experiments": experiments,
        },
        "scope_limitations": [
            "One UCI hourly reference and one chronological 75/25 holdout.",
            "Only training features receive missingness; future test rows and targets remain untouched.",
            "Ridge is a fixed-alpha baseline; no rolling-origin cross-validation or tuning is performed.",
            "casual and registered are excluded as direct target components; day_index is derived and documented.",
        ],
    }
