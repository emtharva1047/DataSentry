"""Tests for the UCI Bike Sharing mixed-type detector experiment."""
import numpy as np
import pandas as pd
import pytest

from app.services import dataset_bike_detector_experiment as module
from app.services.dataset_bike_reference_experiment import (
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
)
from app.services.dataset_research import _infer_numeric_columns


def _semantic_frame(rows: int = 180) -> pd.DataFrame:
    index = np.arange(rows)
    return pd.DataFrame({
        "season": [("season_spring", "season_summer", "season_fall", "season_winter")[i % 4] for i in index],
        "yr": ["year_2011" if i % 2 == 0 else "year_2012" for i in index],
        "mnth": [f"month_{(i % 12) + 1:02d}" for i in index],
        "hr": [f"hour_{i % 24:02d}" for i in index],
        "holiday": ["holiday" if i % 17 == 0 else "not_holiday" for i in index],
        "weekday": [f"weekday_{i % 7}" for i in index],
        "workingday": ["working_day" if i % 7 < 5 else "non_working_day" for i in index],
        "weathersit": [("weather_clear", "weather_mist_cloudy", "weather_light_rain_snow")[i % 3] for i in index],
        "temp": 0.2 + (index % 50) / 100,
        "atemp": 0.25 + (index % 45) / 100,
        "hum": 0.3 + (index % 60) / 100,
        "windspeed": (index % 20) / 100,
        "day_index": index // 24,
    })


def _raw_code_frame() -> pd.DataFrame:
    frame = _semantic_frame()
    code_maps = {
        "season": {"season_spring": "1", "season_summer": "2", "season_fall": "3", "season_winter": "4"},
        "yr": {"year_2011": "0", "year_2012": "1"},
        "mnth": {f"month_{i:02d}": str(i) for i in range(1, 13)},
        "hr": {f"hour_{i:02d}": str(i) for i in range(24)},
        "holiday": {"not_holiday": "0", "holiday": "1"},
        "weekday": {f"weekday_{i}": str(i) for i in range(7)},
        "workingday": {"non_working_day": "0", "working_day": "1"},
        "weathersit": {
            "weather_clear": "1",
            "weather_mist_cloudy": "2",
            "weather_light_rain_snow": "3",
            "weather_heavy_rain_snow": "4",
        },
    }
    for column, mapping in code_maps.items():
        frame[column] = frame[column].map(mapping)
    return frame


def test_detector_reference_maps_integer_codes_to_semantic_categories(monkeypatch):
    raw = _raw_code_frame()
    metadata = {"uci_dataset_id": 275, "rows": len(raw)}
    monkeypatch.setattr(
        module,
        "build_bike_sharing_reference",
        lambda: (raw.copy(deep=True), raw.copy(deep=True), metadata),
    )

    frame, result_metadata = module.build_bike_sharing_detector_reference()

    assert list(frame.columns) == list(raw.columns)
    assert frame["season"].iloc[0] == "season_spring"
    assert frame["yr"].iloc[0] == "year_2011"
    assert frame["hr"].iloc[0] == "hour_00"
    inferred_numeric, _ = _infer_numeric_columns(frame)
    assert set(CATEGORICAL_COLUMNS).isdisjoint(inferred_numeric)
    assert set(NUMERIC_COLUMNS).issubset(inferred_numeric)
    assert result_metadata["target_excluded"] is True
    assert len(result_metadata["detector_frame_sha256"]) == 64
    assert result_metadata["categorical_label_maps"]["season"]["1"] == "season_spring"


def test_detector_reference_rejects_unknown_category_codes(monkeypatch):
    raw = _raw_code_frame()
    raw.loc[0, "season"] = "9"
    monkeypatch.setattr(
        module,
        "build_bike_sharing_reference",
        lambda: (raw, raw.copy(deep=True), {"uci_dataset_id": 275}),
    )
    with pytest.raises(ValueError, match="unsupported category code"):
        module.build_bike_sharing_detector_reference()


def test_bike_detector_benchmark_runs_all_applicable_detectors_for_three_seeds(monkeypatch):
    frame = _semantic_frame()
    metadata = {
        "name": "Bike Sharing test fixture",
        "uci_dataset_id": 275,
        "rows": len(frame),
        "categorical_features": list(CATEGORICAL_COLUMNS),
        "numeric_features": list(NUMERIC_COLUMNS),
    }
    monkeypatch.setattr(
        module,
        "build_bike_sharing_detector_reference",
        lambda: (frame.copy(deep=True), metadata),
    )

    report = module.run_bike_sharing_detector_benchmark(
        rates=(0.05,),
        seeds=(42, 123, 2026),
        n_estimators=10,
    )

    assert report["status"] == "completed"
    assert report["experiment"] == "uci_bike_sharing_synthetic_detector_benchmark"
    assert report["benchmark"]["reference_preflight"]["missing_cells"] == 0
    experiments = report["benchmark"]["experiments"]
    assert len(experiments) == 7
    assert all(item["status"] == "completed" for item in experiments)
    assert all(item["completed_seed_count"] == 3 for item in experiments)
    assert all(item["aggregate"]["seed_count"] == 3 for item in experiments)
    assert {
        item["detector"] for item in experiments
    } == {
        "missingness_rule",
        "exact_duplicate_rule",
        "categorical_consistency_rule",
        "numeric_parseability_rule",
        "iqr",
        "robust_zscore",
        "isolation_forest",
    }
