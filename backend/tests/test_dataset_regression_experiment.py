"""Tests for leakage-safe downstream regression corruption experiments."""
import numpy as np
import pandas as pd
import pytest
from app.services.dataset_regression_experiment import run_regression_corruption_experiment


def _frame(rows=120):
    index = np.arange(rows)
    return pd.DataFrame({
        "temperature": 0.15 + (index % 40) / 100,
        "humidity": 0.30 + (index % 55) / 100,
        "season": np.array(["winter", "spring", "summer", "fall"])[index % 4],
        "target": 80 + 120 * (0.15 + (index % 40) / 100) - 25 * (0.30 + (index % 55) / 100) + (index % 24) * 1.7,
    })


def test_regression_experiment_uses_untouched_chronological_test_and_three_seeds():
    frame = _frame()
    original = frame.copy(deep=True)
    report = run_regression_corruption_experiment(
        frame, target_column="target", numeric_columns=["temperature", "humidity"],
        categorical_columns=["season"], seeds=(42, 123, 2026), test_size=0.25, corruption_rate=0.05,
    )
    assert report["task_type"] == "regression"
    assert report["model"] == "ridge_regression"
    assert report["configuration"]["split_strategy"] == "chronological_ordered_holdout"
    assert all(report["aggregates"][name]["seed_count"] == 3 for name in ("clean", "corrupted", "cleaned_corrupted"))
    assert report["paired_cleaned_minus_corrupted"]["seed_count"] == 3
    fingerprints = set()
    for run in report["per_seed"]:
        split = run["split"]
        assert split["train_rows"] + split["test_rows"] == len(frame)
        assert split["train_positions"][1] < split["test_positions"][0]
        assert split["test_partition_untouched"] is True
        fingerprints.add(split["clean_test_sha256"])
        assert run["corruption"]["injected_cells"] > 0
        assert len(run["corruption"]["ground_truth_sha256"]) == 64
        assert run["cleaning"]["changed"] is True
        assert run["conditions"]["clean"]["metrics"]["mae"] >= 0
        assert run["conditions"]["corrupted"]["metrics"]["rmse"] >= 0
        assert np.isfinite(run["conditions"]["cleaned_corrupted"]["metrics"]["r2"])
    assert len(fingerprints) == 1
    pd.testing.assert_frame_equal(frame, original)


def test_regression_experiment_infers_types_from_clean_training_only():
    report = run_regression_corruption_experiment(_frame(), target_column="target", seeds=(42, 123, 2026), corruption_rate=0.02)
    features = report["per_seed"][0]["features"]
    assert features["type_inference_scope"] == "clean_training_partition_only"
    assert "temperature" in features["numeric_columns"]
    assert "season" in features["categorical_columns"]


def test_regression_experiment_rejects_bad_feature_type_partition():
    with pytest.raises(ValueError, match="partition"):
        run_regression_corruption_experiment(
            _frame(), target_column="target", numeric_columns=["temperature"],
            categorical_columns=["season"], seeds=(42, 123, 2026),
        )


def test_regression_experiment_rejects_missing_and_non_numeric_targets():
    frame = _frame()
    frame.loc[0, "target"] = np.nan
    with pytest.raises(ValueError, match="missing"):
        run_regression_corruption_experiment(frame, target_column="target", seeds=(42, 123, 2026))
    frame = _frame()
    frame["target"] = frame["target"].astype(object)
    frame.loc[0, "target"] = "invalid"
    with pytest.raises(ValueError, match="finite numeric"):
        run_regression_corruption_experiment(frame, target_column="target", seeds=(42, 123, 2026))


def test_regression_experiment_requires_three_distinct_seeds():
    with pytest.raises(ValueError, match="distinct"):
        run_regression_corruption_experiment(_frame(), target_column="target", seeds=(42, 42, 2026))
    with pytest.raises(ValueError, match="between 3 and 10"):
        run_regression_corruption_experiment(_frame(), target_column="target", seeds=(42, 123))
