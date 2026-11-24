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


def test_duplicate_corruption_keeps_feature_target_pairs_aligned_and_cleaning_restores_training():
    frame = _frame()
    original = frame.copy(deep=True)
    report = run_regression_corruption_experiment(
        frame, target_column="target", numeric_columns=["temperature", "humidity"],
        categorical_columns=["season"], seeds=(42, 123, 2026), test_size=0.25,
        corruption_rate=0.05, corruption_type="duplicates",
    )
    assert report["configuration"]["corruption_type"] == "duplicates"
    assert report["configuration"]["split_strategy"] == "chronological_ordered_holdout"
    assert report["aggregates"]["clean"]["seed_count"] == 3
    assert report["aggregates"]["corrupted"]["seed_count"] == 3
    assert report["aggregates"]["cleaned_corrupted"]["seed_count"] == 3
    assert report["paired_cleaned_minus_corrupted"]["seed_count"] == 3
    test_hashes = set()
    for run in report["per_seed"]:
        assert run["split"]["test_partition_untouched"] is True
        test_hashes.add(run["split"]["clean_test_sha256"])
        corruption = run["corruption"]
        assert corruption["injection_unit"] == "source_training_rows"
        assert corruption["injected_rows"] > 0
        assert corruption["injected_count"] == corruption["injected_rows"]
        assert corruption["corrupted_training_rows"] == run["split"]["train_rows"] + corruption["injected_rows"]
        assert corruption["cleaned_training_rows"] == run["split"]["train_rows"]
        assert len(corruption["ground_truth_sha256"]) == 64
        assert len(corruption["ground_truth_records"]) == corruption["injected_rows"]
        assert run["cleaning"]["removed_row_count"] == corruption["injected_rows"]
        assert run["cleaning"]["changed"] is True
        assert run["cleaning"]["operations"][0]["operation"] == "drop_exact_duplicates"
        assert np.isfinite(run["conditions"]["corrupted"]["metrics"]["mae"])
        assert np.isfinite(run["conditions"]["cleaned_corrupted"]["metrics"]["rmse"])
    assert len(test_hashes) == 1
    pd.testing.assert_frame_equal(frame, original)


def test_invalid_value_regression_uses_explicit_production_median_cleaning_and_untouched_test():
    frame = _frame()
    original = frame.copy(deep=True)
    report = run_regression_corruption_experiment(
        frame, target_column="target", numeric_columns=["temperature", "humidity"],
        categorical_columns=["season"], seeds=(42, 123, 2026), test_size=0.25,
        corruption_rate=0.05, corruption_type="invalid_values",
    )
    assert report["configuration"]["corruption_type"] == "invalid_values"
    assert report["schema_version"] == 5
    assert report["aggregates"]["clean"]["seed_count"] == 3
    assert report["aggregates"]["corrupted"]["seed_count"] == 3
    assert report["aggregates"]["cleaned_corrupted"]["seed_count"] == 3
    test_hashes = set()
    for run in report["per_seed"]:
        corruption = run["corruption"]
        assert corruption["injection_unit"] == "eligible_feature_cells"
        assert corruption["injected_cells"] == corruption["injected_count"] > 0
        assert corruption["injected_rows"] is None
        assert sum(corruption["per_column_counts"].values()) == corruption["injected_cells"]
        assert corruption["cleaned_training_rows"] == run["split"]["train_rows"]
        assert run["split"]["test_partition_untouched"] is True
        test_hashes.add(run["split"]["clean_test_sha256"])
        operations = [
            item for item in run["cleaning"]["operations"]
            if item["operation"] == "fill_numeric_median"
        ]
        assert sum(item["invalid_cells_coerced_to_missing"] for item in operations) == corruption["injected_cells"]
        assert sum(item["missing_cells_filled"] for item in operations) == 0
        assert run["cleaning"]["changed"] is True
        assert np.isfinite(run["conditions"]["corrupted"]["metrics"]["rmse"])
        assert np.isfinite(run["conditions"]["cleaned_corrupted"]["metrics"]["mae"])
    assert len(test_hashes) == 1
    pd.testing.assert_frame_equal(frame, original)


def test_regression_experiment_rejects_unsupported_corruption_type():
    with pytest.raises(ValueError, match="corruption_type"):
        run_regression_corruption_experiment(
            _frame(), target_column="target", seeds=(42, 123, 2026),
            corruption_type="not_a_supported_defect",
        )


def test_case_only_categorical_regression_uses_production_lowercase_and_untouched_test():
    frame = _frame()
    original = frame.copy(deep=True)
    report = run_regression_corruption_experiment(
        frame, target_column="target", numeric_columns=["temperature", "humidity"],
        categorical_columns=["season"], seeds=(42, 123, 2026), test_size=0.25,
        corruption_rate=0.05, corruption_type="categorical_inconsistency",
        categorical_mode="case_only",
    )
    assert report["configuration"]["corruption_type"] == "categorical_inconsistency"
    assert report["configuration"]["categorical_mode"] == "case_only"
    assert report["schema_version"] == 5
    test_hashes = set()
    for run in report["per_seed"]:
        corruption = run["corruption"]
        assert corruption["categorical_mode"] == "case_only"
        assert corruption["injected_cells"] == corruption["injected_count"] > 0
        assert corruption["injected_rows"] is None
        assert run["split"]["test_partition_untouched"] is True
        assert run["split"]["cleaned_condition_test_transform"] == "lowercase_categories_on_inference_copy"
        assert run["split"]["test_transform_fitted_parameters"] is False
        test_hashes.add(run["split"]["clean_test_sha256"])
        operations = [
            item for item in run["cleaning"]["operations"]
            if item["operation"] == "lowercase_categories"
        ]
        assert {item["columns"][0] for item in operations} == {"season"}
        assert sum(item["affected_cells"] for item in operations) == corruption["injected_cells"]
        clean_metrics = run["conditions"]["clean"]["metrics"]
        cleaned_metrics = run["conditions"]["cleaned_corrupted"]["metrics"]
        assert all(cleaned_metrics[name] == clean_metrics[name] for name in ("mae", "rmse", "r2"))
        assert np.isfinite(run["conditions"]["corrupted"]["metrics"]["rmse"])
    assert len(test_hashes) == 1
    pd.testing.assert_frame_equal(frame, original)


def test_regression_experiment_rejects_categorical_mode_for_other_defects():
    with pytest.raises(ValueError, match="applies only"):
        run_regression_corruption_experiment(
            _frame(), target_column="target", seeds=(42, 123, 2026),
            corruption_type="missingness", categorical_mode="case_only",
        )


def test_numerical_anomaly_regression_uses_production_iqr_clipping_and_untouched_test():
    frame = _frame()
    original = frame.copy(deep=True)
    report = run_regression_corruption_experiment(
        frame, target_column="target", numeric_columns=["temperature", "humidity"],
        categorical_columns=["season"], seeds=(42, 123, 2026), test_size=0.25,
        corruption_rate=0.05, corruption_type="numerical_anomalies",
    )
    assert report["configuration"]["corruption_type"] == "numerical_anomalies"
    assert report["schema_version"] == 5
    assert all(report["aggregates"][name]["seed_count"] == 3 for name in ("clean", "corrupted", "cleaned_corrupted"))
    assert report["paired_cleaned_minus_corrupted"]["seed_count"] == 3
    test_hashes = set()
    for run in report["per_seed"]:
        corruption = run["corruption"]
        assert corruption["injection_unit"] == "eligible_feature_cells"
        assert corruption["injected_cells"] == corruption["injected_count"] > 0
        assert corruption["injected_rows"] is None
        assert run["corruption"]["cleaned_training_rows"] == run["split"]["train_rows"]
        assert run["split"]["test_partition_untouched"] is True
        test_hashes.add(run["split"]["clean_test_sha256"])
        clip_operations = [
            item for item in run["cleaning"]["operations"]
            if item["operation"] == "clip_numeric_iqr"
        ]
        assert {item["columns"][0] for item in clip_operations} == {"temperature", "humidity"}
        assert sum(item["affected_cells"] for item in clip_operations) >= corruption["injected_cells"]
        assert all(item["review_required"] is True for item in clip_operations)
        assert np.isfinite(run["conditions"]["corrupted"]["metrics"]["rmse"])
        assert np.isfinite(run["conditions"]["cleaned_corrupted"]["metrics"]["mae"])
    assert len(test_hashes) == 1
    pd.testing.assert_frame_equal(frame, original)
