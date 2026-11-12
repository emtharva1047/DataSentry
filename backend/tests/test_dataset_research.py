"""Tests for deterministic synthetic corruption and research metrics."""
import pandas as pd
import pytest

from app.services.dataset_research import (
    SUPPORTED_DEFECTS,
    aggregate_seed_metrics,
    evaluate_binary_detector,
    inject_synthetic_corruption,
)


def _reference_frame(rows: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "amount": [float(index + 1) for index in range(rows)],
            "units": [float((index * 7) % 31 + 1) for index in range(rows)],
            "city": [("north", "south", "east", "west")[index % 4] for index in range(rows)],
            "segment": [("retail", "business")[index % 2] for index in range(rows)],
        }
    )


def test_all_five_corruptions_return_exact_cell_and_row_labels():
    original = _reference_frame()
    original_copy = original.copy(deep=True)

    result = inject_synthetic_corruption(original, rate=0.10, seed=23)

    assert result.frame.shape == (110, 4)
    assert result.ground_truth["source_shape"] == {"rows": 100, "columns": 4}
    assert result.ground_truth["corrupted_shape"] == {"rows": 110, "columns": 4}
    assert result.ground_truth["selected_defects"] == list(SUPPORTED_DEFECTS)
    assert result.ground_truth["seed"] == 23
    assert result.ground_truth["rate"] == 0.10
    assert result.ground_truth["defects"]["duplicates"]["injected_count"] == 10

    for defect in SUPPORTED_DEFECTS:
        assert result.ground_truth["defects"][defect]["status"] == "completed"
        assert result.ground_truth["defects"][defect]["injected_count"] > 0

    for record in result.ground_truth["duplicate_rows"]:
        assert record["row_index"] >= len(original)
        assert record["data_row_number"] == record["row_index"] + 1
        assert (
            result.frame.iloc[record["row_index"]].tolist()
            == original.iloc[record["source_row_index"]].tolist()
        )

    for record in result.ground_truth["cell_labels"]:
        row_index = record["row_index"]
        column = record["column"]
        corrupted_value = result.frame.iloc[row_index][column]
        original_value = original.iloc[row_index][column]
        assert record["data_row_number"] == row_index + 1
        if record["defect_type"] == "missingness":
            assert pd.isna(corrupted_value)
        elif record["defect_type"] == "categorical_inconsistency":
            assert corrupted_value != original_value
            assert corrupted_value.strip().swapcase() == original_value.strip()
        elif record["defect_type"] == "invalid_values":
            assert corrupted_value == result.ground_truth["invalid_value_token"]
        elif record["defect_type"] == "numerical_anomalies":
            assert float(corrupted_value) > float(original[column].max())

    labeled_cell_count = sum(
        result.ground_truth["defects"][name]["injected_count"]
        for name in (
            "missingness",
            "categorical_inconsistency",
            "invalid_values",
            "numerical_anomalies",
        )
    )
    assert len(result.ground_truth["cell_labels"]) == labeled_cell_count
    assert result.ground_truth["row_labels"]
    pd.testing.assert_frame_equal(original, original_copy)


def test_corruption_is_deterministic_for_the_same_seed():
    frame = _reference_frame()
    first = inject_synthetic_corruption(frame, rate=0.05, seed=42)
    second = inject_synthetic_corruption(frame, rate=0.05, seed=42)

    pd.testing.assert_frame_equal(first.frame, second.frame)
    assert first.ground_truth == second.ground_truth


def test_defect_selection_and_ineligible_columns_are_reported_without_fabricating_labels():
    frame = pd.DataFrame({"category": ["north", "south", "east", "west"]})
    result = inject_synthetic_corruption(
        frame,
        rate=0.10,
        seed=7,
        defects=["numerical_anomalies", "invalid_values"],
    )

    assert result.ground_truth["defects"]["missingness"]["status"] == "not_selected"
    assert result.ground_truth["defects"]["numerical_anomalies"]["status"] == "skipped"
    assert result.ground_truth["defects"]["invalid_values"]["status"] == "skipped"
    assert result.ground_truth["cell_labels"] == []
    pd.testing.assert_frame_equal(result.frame, frame.astype(object))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rate": 0}, "rate must be greater than 0"),
        ({"rate": 0.75}, "rate must be greater than 0"),
        ({"seed": -1}, "seed must be an integer"),
        ({"defects": ["unknown"]}, "unsupported corruption type"),
        ({"defects": ["missingness", "missingness"]}, "must not contain duplicates"),
        ({"defects": []}, "select at least one corruption type"),
    ],
)
def test_corruption_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        inject_synthetic_corruption(_reference_frame(), **kwargs)


def test_corruption_rejects_duplicate_column_names():
    frame = pd.DataFrame([[1, 2], [3, 4]], columns=["value", "value"])
    with pytest.raises(ValueError, match="unique column names"):
        inject_synthetic_corruption(frame, rate=0.1, seed=1)


def test_binary_detector_metrics_include_exact_confusion_counts():
    report = evaluate_binary_detector(
        ground_truth=[1, 1, 0, 0],
        predictions=[1, 0, 1, 0],
    )

    assert report["confusion_counts"] == {
        "true_positive": 1,
        "false_positive": 1,
        "true_negative": 1,
        "false_negative": 1,
    }
    assert report["precision"] == 0.5
    assert report["recall"] == 0.5
    assert report["f1"] == 0.5
    assert report["accuracy"] == 0.5
    assert report["support"] == 2


def test_binary_detector_zero_division_is_explicit():
    report = evaluate_binary_detector([0, 0, 0], [0, 0, 0])

    assert report["precision"] == 0
    assert report["recall"] == 0
    assert report["f1"] == 0
    assert report["accuracy"] == 1
    assert report["zero_division_convention"] == 0


@pytest.mark.parametrize(
    ("truth", "predictions", "message"),
    [
        ([], [], "non-empty"),
        ([1, 0], [1], "equal lengths"),
        ([1, 2], [1, 0], "binary 0/1"),
    ],
)
def test_binary_detector_rejects_invalid_inputs(truth, predictions, message):
    with pytest.raises(ValueError, match=message):
        evaluate_binary_detector(truth, predictions)


def test_seed_aggregation_reports_mean_and_sample_standard_deviation():
    report = aggregate_seed_metrics(
        [
            {"seed": 7, "metrics": {"precision": 0.5, "f1": 0.4}},
            {"seed": 17, "metrics": {"precision": 0.7, "f1": 0.5}},
            {"seed": 42, "metrics": {"precision": 0.9, "f1": 0.6}},
        ]
    )

    assert report["seed_count"] == 3
    assert report["seeds"] == [7, 17, 42]
    assert report["metrics"]["precision"]["mean"] == 0.7
    assert report["metrics"]["precision"]["sample_standard_deviation"] == 0.2
    assert report["metrics"]["f1"]["mean"] == 0.5
    assert report["metrics"]["f1"]["sample_standard_deviation"] == 0.1


def test_seed_aggregation_requires_three_distinct_seeds_and_matching_metrics():
    with pytest.raises(ValueError, match="at least 3 distinct"):
        aggregate_seed_metrics(
            [
                {"seed": 1, "metrics": {"f1": 0.5}},
                {"seed": 2, "metrics": {"f1": 0.6}},
            ]
        )
    with pytest.raises(ValueError, match="distinct integers"):
        aggregate_seed_metrics(
            [
                {"seed": 1, "metrics": {"f1": 0.5}},
                {"seed": 1, "metrics": {"f1": 0.6}},
                {"seed": 3, "metrics": {"f1": 0.7}},
            ]
        )
    with pytest.raises(ValueError, match="same metric names"):
        aggregate_seed_metrics(
            [
                {"seed": 1, "metrics": {"f1": 0.5}},
                {"seed": 2, "metrics": {"precision": 0.6}},
                {"seed": 3, "metrics": {"f1": 0.7}},
            ]
        )
