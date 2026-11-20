"""Tests for isolated pure case-only public-reference evaluation."""
import pandas as pd

from app.services import dataset_case_only_experiment as module
from app.services.dataset_benchmark import run_synthetic_detector_benchmark
from app.services.dataset_research import inject_synthetic_corruption


def _reference_frame(rows=120):
    index = range(rows)
    return pd.DataFrame({
        "amount": [float(value + 1) for value in index],
        "units": [float((value * 17) % 101 + 1) for value in index],
        "city": [("north", "south", "east", "west")[value % 4] for value in index],
        "segment": [("retail", "business")[value % 2] for value in index],
    })


def test_case_only_corruption_changes_case_without_adding_whitespace():
    original = _reference_frame()
    result = inject_synthetic_corruption(
        original,
        rate=0.05,
        seed=42,
        defects=("categorical_inconsistency",),
        categorical_mode="case_only",
    )

    assert result.ground_truth["schema_version"] == 2
    assert result.ground_truth["categorical_corruption_mode"] == "case_only"
    labels = result.ground_truth["cell_labels"]
    assert labels
    for label in labels:
        before = original.iloc[label["row_index"]][label["column"]]
        after = result.frame.iloc[label["row_index"]][label["column"]]
        assert after == before.swapcase()
        assert after == after.strip()
    pd.testing.assert_frame_equal(original, _reference_frame())


def test_case_only_benchmark_uses_production_detector_and_exact_labels():
    report = run_synthetic_detector_benchmark(
        _reference_frame(),
        rates=(0.01, 0.05, 0.10),
        seeds=(42, 123, 2026),
        defects=("categorical_inconsistency",),
        categorical_mode="case_only",
    )

    assert report["configuration"]["categorical_mode"] == "case_only"
    assert report["configuration"]["ground_truth_schema_version"] == 2
    assert len(report["experiments"]) == 3
    assert all(item["status"] == "completed" for item in report["experiments"])
    assert all(item["aggregate"]["seed_count"] == 3 for item in report["experiments"])
    assert all(item["aggregate"]["metrics"]["f1"]["mean"] == 1.0 for item in report["experiments"])


def test_case_only_public_runner_keeps_both_reference_reports(monkeypatch):
    frame = _reference_frame()
    metadata = {"rows": len(frame), "source": "deterministic test fixture"}
    monkeypatch.setattr(module, "build_wine_reference", lambda: (frame.copy(), frame.copy(), metadata))
    monkeypatch.setattr(module, "build_bike_sharing_detector_reference", lambda: (frame.copy(), metadata))

    report = module.run_case_only_public_reference_benchmark(
        rates=(0.05,),
        seeds=(42, 123, 2026),
    )

    assert report["status"] == "completed"
    assert report["configuration"]["categorical_mode"] == "case_only"
    assert set(report["references"]) == {"uci_wine", "uci_bike_sharing"}
    assert all(item["status"] == "completed" for item in report["references"].values())
