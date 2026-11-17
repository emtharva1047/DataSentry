"""Tests for UCI Bike Sharing provenance and mixed-type regression reference."""
from io import BytesIO
from zipfile import ZipFile
import numpy as np
import pandas as pd
import pytest
from app.services.dataset_bike_reference_experiment import (
    CATEGORICAL_COLUMNS, NUMERIC_COLUMNS, _build_from_archive,
)
from app.services import dataset_bike_reference_experiment as module


def _source(rows=120):
    index = np.arange(rows)
    dates = pd.date_range("2011-01-01", periods=(rows + 23) // 24, freq="D")
    day = index // 24
    casual = 1 + index % 13
    registered = 20 + index % 31
    return pd.DataFrame({
        "instant": index + 1, "dteday": dates[day].strftime("%Y-%m-%d"),
        "season": index % 4 + 1, "yr": day % 2, "mnth": day % 12 + 1,
        "hr": index % 24, "holiday": index % 2, "weekday": day % 7,
        "workingday": (day % 7 < 5).astype(int), "weathersit": index % 4 + 1,
        "temp": 0.2 + index % 50 / 100, "atemp": 0.25 + index % 45 / 100,
        "hum": 0.3 + index % 60 / 100, "windspeed": index % 20 / 100,
        "casual": casual, "registered": registered, "cnt": casual + registered,
    })


def _zip(frame):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("Bike-Sharing-Dataset/hour.csv", frame.to_csv(index=False))
    return buffer.getvalue()


def test_bike_reference_builds_mixed_features_and_excludes_target_components():
    source = _source()
    features, full, metadata = _build_from_archive(_zip(source), minimum_rows=30)
    assert features.shape == (120, 13)
    assert full.shape == (120, 14)
    assert set(CATEGORICAL_COLUMNS).issubset(features.columns)
    assert set(NUMERIC_COLUMNS).issubset(features.columns)
    assert not {"casual", "registered", "instant", "dteday"} & set(features.columns)
    assert features["season"].map(type).eq(str).all()
    assert np.issubdtype(features["temp"].dtype, np.number)
    assert metadata["uci_dataset_id"] == 275
    assert metadata["rows"] == 120
    assert metadata["target_column"] == "cnt"
    assert metadata["retrieval_mode"] == "provided_archive"
    assert len(metadata["archive_sha256"]) == 64
    assert len(metadata["hour_csv_sha256"]) == 64
    assert metadata["derived_features"][0]["name"] == "day_index"
    assert full["cnt"].equals(source["cnt"].astype(float))


def test_bike_reference_rejects_inconsistent_target_components():
    source = _source()
    source.loc[0, "cnt"] += 1
    with pytest.raises(ValueError, match="casual plus registered"):
        _build_from_archive(_zip(source), minimum_rows=30)


def test_bike_reference_rejects_archive_without_hour_csv():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("day.csv", "instant,cnt\n1,2\n")
    with pytest.raises(ValueError, match="exactly one hour.csv"):
        _build_from_archive(buffer.getvalue(), minimum_rows=30)


def test_bike_regression_runs_three_seeds_with_untouched_future_test(monkeypatch):
    payload = _zip(_source())
    monkeypatch.setattr(module, "build_bike_sharing_reference", lambda: module._build_from_archive(payload, minimum_rows=30, retrieval_mode="provided_archive"))
    report = module.run_bike_sharing_regression_experiment(
        rates=(0.05,), seeds=(42, 123, 2026), test_size=0.25,
    )
    assert report["dataset"]["uci_dataset_id"] == 275
    assert report["downstream_regression"]["corruption_rates"] == [0.05]
    experiment = report["downstream_regression"]["experiments"][0]
    assert experiment["configuration"]["split_strategy"] == "chronological_ordered_holdout"
    assert all(experiment["aggregates"][name]["seed_count"] == 3 for name in ("clean", "corrupted", "cleaned_corrupted"))
    assert len({run["split"]["clean_test_sha256"] for run in experiment["per_seed"]}) == 1
    assert all(run["split"]["test_partition_untouched"] for run in experiment["per_seed"])
    assert all(run["corruption"]["injected_cells"] > 0 and run["cleaning"]["changed"] for run in experiment["per_seed"])
