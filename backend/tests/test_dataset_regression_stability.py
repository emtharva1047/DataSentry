"""Tests for rolling-origin clean-baseline stability evaluation."""
import numpy as np
import pandas as pd
import pytest

from app.services.dataset_regression_stability import (
    run_rolling_origin_baseline_stability,
)


def _frame(rows=120):
    index = np.arange(rows)
    return pd.DataFrame({
        "temperature": 0.15 + (index % 40) / 100,
        "humidity": 0.30 + (index % 55) / 100,
        "season": np.array(["winter", "spring", "summer", "fall"])[index % 4],
        "target": 80 + 120 * (0.15 + (index % 40) / 100)
        - 25 * (0.30 + (index % 55) / 100) + (index % 24) * 1.7,
    })


def test_rolling_origin_reports_three_non_overlapping_future_windows_and_uncertainty():
    frame = _frame()
    original = frame.copy(deep=True)
    report = run_rolling_origin_baseline_stability(
        frame,
        target_column="target",
        numeric_columns=["temperature", "humidity"],
        categorical_columns=["season"],
    )

    assert report["evaluation"] == "clean_baseline_rolling_origin_stability"
    assert report["model"] == "ridge_regression"
    assert report["configuration"]["uncertainty_basis"] == (
        "sample_standard_deviation_across_non_overlapping_future_windows"
    )
    assert report["configuration"]["random_seed"] is None
    assert report["aggregates"]["window_count"] == 3
    assert len(report["per_window"]) == 3

    expected_ranges = [([0, 83], [84, 95]), ([0, 95], [96, 107]), ([0, 107], [108, 119])]
    hashes = set()
    for run, (train_range, test_range) in zip(report["per_window"], expected_ranges):
        split = run["split"]
        assert split["train_positions"] == train_range
        assert split["test_positions"] == test_range
        assert split["train_rows"] == train_range[1] + 1
        assert split["test_rows"] == test_range[1] - test_range[0] + 1
        assert split["test_partition_untouched"] is True
        assert split["preprocessing_fit_scope"] == "training_partition_only"
        hashes.add(split["clean_test_sha256"])
        assert np.isfinite(run["metrics"]["mae"])
        assert np.isfinite(run["metrics"]["rmse"])
        assert np.isfinite(run["metrics"]["r2"])
    assert len(hashes) == 3

    values = [run["metrics"]["mae"] for run in report["per_window"]]
    aggregate = report["aggregates"]["metrics"]["mae"]
    assert aggregate["mean"] == round(float(np.mean(values)), 6)
    assert aggregate["sample_std"] == round(float(np.std(values, ddof=1)), 6)
    pd.testing.assert_frame_equal(frame, original)


def test_rolling_origin_infers_feature_types_from_each_training_prefix():
    report = run_rolling_origin_baseline_stability(_frame(), target_column="target")
    for run in report["per_window"]:
        assert run["features"]["type_inference_scope"] == "current_training_prefix_only"
        assert "temperature" in run["features"]["numeric_columns"]
        assert "season" in run["features"]["categorical_columns"]


def test_rolling_origin_rejects_overlapping_future_windows():
    with pytest.raises(ValueError, match="must not overlap"):
        run_rolling_origin_baseline_stability(
            _frame(), target_column="target",
            train_fractions=(0.60, 0.65, 0.80),
            test_window_fraction=0.10,
        )


def test_rolling_origin_rejects_bad_feature_partition():
    with pytest.raises(ValueError, match="partition"):
        run_rolling_origin_baseline_stability(
            _frame(), target_column="target",
            numeric_columns=["temperature"],
            categorical_columns=["season"],
        )


def test_rolling_origin_rejects_non_finite_target_and_dirty_reference():
    frame = _frame()
    frame.loc[0, "target"] = np.nan
    with pytest.raises(ValueError, match="missing"):
        run_rolling_origin_baseline_stability(frame, target_column="target")
    frame = _frame()
    frame.loc[0, "season"] = " "
    with pytest.raises(ValueError, match="missing or whitespace-only"):
        run_rolling_origin_baseline_stability(frame, target_column="target")
