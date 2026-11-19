"""Tests for Isolation Forest contamination sensitivity on Bike Sharing."""
import numpy as np
import pandas as pd
import pytest

from app.services import dataset_bike_contamination_sensitivity as module
from app.services.dataset_bike_reference_experiment import (
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
)


def _semantic_frame(rows: int = 240) -> pd.DataFrame:
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
        "temp": 0.2 + index * 0.0001,
        "atemp": 0.25 + index * 0.00012,
        "hum": 0.3 + (index % 80) / 100,
        "windspeed": (index % 60) / 100,
        "day_index": index / 24,
    })


def test_contamination_sweep_reports_actual_row_prevalence_and_control_invariance(monkeypatch):
    frame = _semantic_frame()
    metadata = {
        "name": "Bike Sharing sensitivity test fixture",
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

    report = module.run_bike_sharing_contamination_sensitivity(
        rates=(0.05,),
        seeds=(42, 123, 2026),
        contamination_values=(0.01, 0.05, 0.10),
        n_estimators=10,
    )

    assert report["status"] == "completed"
    assert report["experiment"] == "uci_bike_sharing_isolation_forest_contamination_sensitivity"
    assert len(report["sweeps"]) == 3
    assert all(sweep["status"] == "completed" for sweep in report["sweeps"])
    assert all(len(sweep["experiments"]) == 3 for sweep in report["sweeps"])

    for sweep in report["sweeps"]:
        isolation = next(item for item in sweep["experiments"] if item["detector"] == "isolation_forest")
        assert isolation["completed_seed_count"] == 3
        assert isolation["prevalence_aggregate"]["seed_count"] == 3
        for run in isolation["runs"]:
            assert 0 < run["ground_truth_row_prevalence"] <= 1
            assert 0 <= run["predicted_row_prevalence"] <= 1
            counts = run["confusion_counts"]
            assert run["ground_truth_positive_rows"] == counts["true_positive"] + counts["false_negative"]
            assert run["predicted_positive_rows"] == counts["true_positive"] + counts["false_positive"]

    for detector in ("iqr", "robust_zscore"):
        assert report["control_checks"][detector]["0.05"]["invariant_across_contamination"] is True


@pytest.mark.parametrize(
    "values",
    [
        (),
        (0.05,),
        (0.01, 0.01),
        (0.0, 0.05),
        (0.05, 0.6),
        (True, 0.05),
        (float("nan"), 0.05),
    ],
)
def test_contamination_sweep_rejects_invalid_settings(monkeypatch, values):
    monkeypatch.setattr(
        module,
        "build_bike_sharing_detector_reference",
        lambda: pytest.fail("invalid settings must be rejected before dataset loading"),
    )
    with pytest.raises(ValueError):
        module.run_bike_sharing_contamination_sensitivity(contamination_values=values)
