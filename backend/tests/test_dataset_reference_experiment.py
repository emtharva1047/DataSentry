"""Tests for the public reference and clean-test downstream experiment."""
import pandas as pd
import pytest

from app.services.dataset_ml_experiment import run_classification_corruption_experiment
from app.services.dataset_reference_experiment import (
    build_wine_reference,
    run_wine_reference_experiment,
)


def _mixed_classification_frame(rows: int = 120) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "amount": [float(index + 1) for index in range(rows)],
            "units": [float((index * 17) % 101 + 1) for index in range(rows)],
            "segment": [("north", "south", "east", "west")[index % 4] for index in range(rows)],
            "target": [("a", "b", "c")[index % 3] for index in range(rows)],
        }
    )


def test_classification_experiment_uses_same_untouched_test_and_production_cleaner():
    frame = _mixed_classification_frame()
    original = frame.copy(deep=True)

    report = run_classification_corruption_experiment(
        frame,
        target_column="target",
        seeds=(42, 123, 2026),
        test_size=0.25,
        corruption_rate=0.05,
    )

    assert report["configuration"]["seeds"] == [42, 123, 2026]
    assert set(report["aggregates"]) == {"clean", "corrupted", "cleaned_corrupted"}
    assert report["paired_cleaned_minus_corrupted_macro_f1"]["seed_count"] == 3
    assert len(report["per_seed"]) == 3

    for run in report["per_seed"]:
        assert run["split"]["test_partition_untouched"] is True
        assert run["split"]["train_rows"] + run["split"]["test_rows"] == len(frame)
        assert run["corruption"]["injected_count"] > 0
        assert run["cleaning"]["changed"] is True
        assert run["cleaning"]["rows_before"] == run["cleaning"]["rows_after"]
        assert run["conditions"]["clean"]["confusion_matrix"]["counts"]
        assert run["conditions"]["corrupted"]["metrics"]["macro_f1"] >= 0
        assert run["conditions"]["cleaned_corrupted"]["metrics"]["macro_f1"] >= 0

    assert report["aggregates"]["clean"]["seed_count"] == 3
    assert report["aggregates"]["corrupted"]["seed_count"] == 3
    assert report["aggregates"]["cleaned_corrupted"]["seed_count"] == 3
    pd.testing.assert_frame_equal(frame, original)


def test_classification_experiment_rejects_unclean_reference():
    frame = _mixed_classification_frame()
    frame.loc[0, "amount"] = None

    with pytest.raises(ValueError, match="must not contain missing"):
        run_classification_corruption_experiment(
            frame,
            target_column="target",
            seeds=(42, 123, 2026),
        )


def test_wine_reference_provenance_and_derived_categorical_feature():
    features, full_frame, metadata = build_wine_reference()

    assert features.shape == (178, 14)
    assert full_frame.shape == (178, 15)
    assert metadata["uci_dataset_id"] == 109
    assert metadata["original_numeric_features"] == 13
    assert metadata["derived_features"][0]["name"] == "alcohol_band"
    assert metadata["derived_features"][0]["is_original_dataset_feature"] is False
    assert metadata["class_distribution"] == {"0": 59, "1": 71, "2": 48}
    assert features["alcohol_band"].nunique() == 3
    assert not full_frame.isna().any().any()
    assert not full_frame.duplicated().any()
    assert len(metadata["sha256_full_frame"]) == 64


def test_public_wine_reference_runs_detector_and_clean_test_experiments():
    report = run_wine_reference_experiment(
        rates=(0.05,),
        seeds=(42, 123, 2026),
        n_estimators=20,
    )

    assert report["dataset"]["rows"] == 178
    assert report["detector_benchmark"]["reference_preflight"]["missing_cells"] == 0
    assert report["detector_benchmark"]["reference_preflight"]["duplicate_rows"] == 0
    assert len(report["detector_benchmark"]["experiments"]) == 7
    for experiment in report["detector_benchmark"]["experiments"]:
        assert experiment["status"] == "completed"
        assert experiment["completed_seed_count"] == 3
        assert experiment["aggregate"]["seed_count"] == 3

    downstream = report["downstream_classification"]
    assert downstream["configuration"]["seeds"] == [42, 123, 2026]
    assert downstream["configuration"]["selected_feature_columns"] == ["alcohol_band"]
    assert downstream["paired_cleaned_minus_corrupted_macro_f1"]["seed_count"] == 3
    assert all(
        run["split"]["test_partition_untouched"]
        for run in downstream["per_seed"]
    )
