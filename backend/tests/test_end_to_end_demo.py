"""Integration coverage for the reproducible upload-to-baseline demo."""
from pathlib import Path

from scripts.run_end_to_end_demo import run_demo


def test_end_to_end_demo_uses_isolated_storage_and_preserves_original(tmp_path: Path) -> None:
    report = run_demo(tmp_path / "demo")

    assert report["status"] == "passed"
    assert report["demo_type"] == "api_integration_not_browser_e2e"
    assert report["dataset"]["source_rows"] == 61
    assert report["dataset"]["cleaned_rows"] == 60
    assert report["quality"]["issue_count"] > 0
    assert report["cleaning"]["version_number"] == 1
    assert report["cleaning"]["source_preserved"] is True
    assert report["original_source_preserved"] is True
    assert report["baseline"]["preprocessing_fit_scope"] == "training_partition_only"
    assert report["baseline"]["test_partition_used_to_fit_preprocessing"] is False
    assert {"mae", "rmse", "r2"} == set(report["baseline"]["metrics"])
    assert len(report["steps"]) >= 14
    assert (tmp_path / "demo" / "uploads").is_dir()
    assert (tmp_path / "demo" / "versions").is_dir()
    assert not (tmp_path / "demo" / "datasentry.db").exists()
