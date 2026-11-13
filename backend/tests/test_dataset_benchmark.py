"""Tests for the ground-truth detector benchmark runner."""
import pandas as pd
import pytest

from app.services.dataset_benchmark import run_synthetic_detector_benchmark


def _reference_frame(rows: int = 120) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "amount": [float(index + 1) for index in range(rows)],
            "units": [float((index * 17) % 101 + 1) for index in range(rows)],
            "city": [("north", "south", "east", "west")[index % 4] for index in range(rows)],
            "segment": [("retail", "business")[index % 2] for index in range(rows)],
        }
    )


def test_benchmark_connects_all_defects_to_applicable_detectors_and_three_seeds():
    frame = _reference_frame()
    original = frame.copy(deep=True)

    report = run_synthetic_detector_benchmark(
        frame,
        rates=(0.05,),
        seeds=(42, 123, 2026),
        n_estimators=50,
    )

    assert report["schema_version"] == 1
    assert report["configuration"]["seeds"] == [42, 123, 2026]
    assert len(report["experiments"]) == 7
    assert {item["defect_type"] for item in report["experiments"]} == {
        "missingness",
        "duplicates",
        "categorical_inconsistency",
        "invalid_values",
        "numerical_anomalies",
    }

    by_key = {
        (item["defect_type"], item["detector"]): item
        for item in report["experiments"]
    }
    assert by_key[("missingness", "missingness_rule")]["status"] == "completed"
    assert by_key[("missingness", "missingness_rule")]["aggregate"]["seed_count"] == 3
    assert by_key[("missingness", "missingness_rule")]["aggregate"]["metrics"]["f1"]["mean"] == 1.0
    assert by_key[("duplicates", "exact_duplicate_rule")]["aggregate"]["metrics"]["f1"]["mean"] == 1.0
    assert by_key[("invalid_values", "numeric_parseability_rule")]["aggregate"]["metrics"]["f1"]["mean"] == 1.0

    for item in report["experiments"]:
        assert item["status"] == "completed"
        assert item["completed_seed_count"] == 3
        assert item["aggregate"]["seed_count"] == 3
        assert item["aggregate"]["seeds"] == [42, 123, 2026]
        assert len(item["runs"]) == 3
        for run in item["runs"]:
            assert run["injected_count"] > 0
            assert set(run["confusion_counts"]) == {
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            }
            assert 0 <= run["metrics"]["precision"] <= 1
            assert 0 <= run["metrics"]["recall"] <= 1
            assert 0 <= run["metrics"]["f1"] <= 1
            assert run["metrics"]["runtime_seconds"] >= 0
            assert run["metrics"]["python_tracemalloc_peak_bytes"] >= 0

    pd.testing.assert_frame_equal(frame, original)


def test_benchmark_keeps_ineligible_detector_runs_visible_without_aggregating():
    frame = pd.DataFrame({"category": ["north", "south", "east", "west"] * 10})

    report = run_synthetic_detector_benchmark(
        frame,
        rates=(0.05,),
        seeds=(1, 2, 3),
        defects=("numerical_anomalies",),
    )

    assert len(report["experiments"]) == 3
    for item in report["experiments"]:
        assert item["status"] == "incomplete"
        assert item["completed_seed_count"] == 0
        assert item["aggregate"] is None
        assert len(item["skipped_runs"]) == 3
        assert all(run["reason"] for run in item["skipped_runs"])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"seeds": (1, 2)}, "between 3 and 10"),
        ({"seeds": (1, 1, 2)}, "distinct"),
        ({"rates": (0.01, 0.01)}, "distinct"),
        ({"rates": (0.75,)}, "in \\(0, 0.5\\]"),
        ({"defects": ("unknown",)}, "unsupported defect"),
        ({"n_estimators": 0}, "between 1 and 500"),
        ({"contamination": 0.8}, "at most 0.5"),
    ],
)
def test_benchmark_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        run_synthetic_detector_benchmark(_reference_frame(), **kwargs)

def test_benchmark_reports_clean_reference_preflight():
    report = run_synthetic_detector_benchmark(
        _reference_frame(),
        rates=(0.05,),
        seeds=(42, 123, 2026),
        defects=("missingness",),
    )

    preflight = report["reference_preflight"]
    assert preflight["missing_cells"] == 0
    assert preflight["duplicate_rows"] == 0
    assert preflight["categorical_inconsistency_cells"] == 0
    assert preflight["invalid_numeric_cells"] == 0
    assert preflight["numeric_columns"] == ["amount", "units"]
    assert preflight["statistical_outliers_rejected"] is False


@pytest.mark.parametrize(
    ("defect", "expected_finding"),
    [
        ("missingness", "missing_cells=1"),
        ("duplicates", "duplicate_rows=1"),
        ("categorical_inconsistency", "categorical_inconsistency_cells"),
        ("invalid_values", "invalid_numeric_cells=1"),
    ],
)
def test_benchmark_rejects_preexisting_deterministic_defects(defect, expected_finding):
    frame = _reference_frame()
    if defect == "missingness":
        frame.loc[0, "amount"] = None
    elif defect == "duplicates":
        frame.loc[1] = frame.loc[0]
    elif defect == "categorical_inconsistency":
        frame.loc[0, "city"] = " NORTH "
    elif defect == "invalid_values":
        frame.loc[0, "amount"] = "not-a-number"

    with pytest.raises(ValueError, match=expected_finding):
        run_synthetic_detector_benchmark(
            frame,
            rates=(0.05,),
            seeds=(42, 123, 2026),
            defects=("missingness",),
        )

