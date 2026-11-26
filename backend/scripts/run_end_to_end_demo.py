"""Run a deterministic API-level DataSentry demo with isolated SQLite and file storage."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as api_module
from app.database import Base, get_db
from app.main import app
from app.services import dataset_cleaning, dataset_ingestion


def _sample_csv() -> bytes:
    """Build a small deterministic fixture with reviewable quality defects."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["amount", "city", "spend"])
    rows: list[list[str]] = []

    for index in range(60):
        base_amount = 12.0 + index * 1.25
        amount = "" if index == 12 else (
            "5000.00" if index == 55 else f"{base_amount:.2f}"
        )
        city = ("North", "South", "East", "West")[index % 4]
        if index == 4:
            city = " North "
        elif index == 5:
            city = "north"
        spend = f"{base_amount * 1.8 + (index % 5) * 3.0:.2f}"
        row = [amount, city, spend]
        rows.append(row)
        writer.writerow(row)

    # The appended row is an exact duplicate, not a near-duplicate.
    writer.writerow(rows[2])
    return output.getvalue().encode("utf-8")


def _request(
    client: TestClient,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
    **kwargs: Any,
) -> dict[str, Any] | list[Any]:
    response = client.request(method, path, **kwargs)
    if response.status_code != expected_status:
        detail = response.text[:1000]
        raise RuntimeError(
            f"{method} {path} returned HTTP {response.status_code}; "
            f"expected {expected_status}: {detail}"
        )
    return response.json()


def run_demo(work_dir: Path) -> dict[str, Any]:
    """Exercise the upload-to-baseline API journey without persistent app data.

    The work directory must be empty. SQLite is held in memory; uploaded and
    derived CSVs are confined to the supplied temporary directory.
    """
    work_dir = work_dir.expanduser().resolve()
    if work_dir.exists() and any(work_dir.iterdir()):
        raise ValueError("The demo work directory must be empty.")
    work_dir.mkdir(parents=True, exist_ok=True)

    upload_dir = work_dir / "uploads"
    version_dir = work_dir / "versions"
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )
    Base.metadata.create_all(bind=test_engine)

    previous_overrides = app.dependency_overrides.copy()
    previous_initialize = api_module.initialize_database
    previous_upload_dir = dataset_ingestion.UPLOAD_DIR
    previous_version_dir = dataset_cleaning.VERSIONS_DIR

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    api_module.initialize_database = lambda: None
    dataset_ingestion.UPLOAD_DIR = upload_dir
    dataset_cleaning.VERSIONS_DIR = version_dir

    try:
        with TestClient(app) as client:
            steps: list[dict[str, str]] = []

            health = _request(client, "GET", "/api/health")
            if health.get("status") != "ok":
                raise RuntimeError("The API health response was not healthy.")
            steps.append({"name": "health", "status": "passed"})

            overview_before = _request(client, "GET", "/api/overview")
            if overview_before.get("dataset_count") != 0:
                raise RuntimeError("The isolated demo database was not empty.")
            steps.append({"name": "empty_overview", "status": "passed"})

            payload = _sample_csv()
            source_sha256 = hashlib.sha256(payload).hexdigest()
            dataset = _request(
                client,
                "POST",
                "/api/datasets/upload",
                expected_status=201,
                files={"file": ("datasentry-demo.csv", payload, "text/csv")},
            )
            dataset_id = int(dataset["id"])
            if dataset.get("sha256_hash") != source_sha256:
                raise RuntimeError("The upload fingerprint did not match its bytes.")
            steps.append({"name": "csv_upload", "status": "passed"})

            listed = _request(client, "GET", "/api/datasets")
            if not any(int(item["id"]) == dataset_id for item in listed):
                raise RuntimeError("The uploaded dataset was not present in the library.")
            detail = _request(client, "GET", f"/api/datasets/{dataset_id}")
            if detail.get("sha256_hash") != source_sha256:
                raise RuntimeError("Dataset detail did not preserve the upload fingerprint.")
            steps.append({"name": "dataset_list_and_detail", "status": "passed"})

            profile = _request(client, "GET", f"/api/datasets/{dataset_id}/profile")
            if profile.get("shape", {}).get("rows") != 61:
                raise RuntimeError("The profile did not report the expected 61 source rows.")
            steps.append({"name": "profiling", "status": "passed"})

            quality = _request(client, "GET", f"/api/datasets/{dataset_id}/quality")
            dqs = quality.get("data_quality_score", {})
            if quality.get("issue_count", 0) < 1 or dqs.get("overall") is None:
                raise RuntimeError("The quality assessment did not return issue evidence and DQS.")
            steps.append({"name": "quality_and_dqs", "status": "passed"})

            schema = _request(
                client,
                "POST",
                f"/api/datasets/{dataset_id}/quality/validate",
                json={
                    "columns": {
                        "amount": {
                            "type": "number",
                            "required": True,
                            "minimum": 0,
                            "maximum": 1000,
                        },
                        "city": {
                            "type": "string",
                            "required": True,
                            "allowed_values": ["North", "South", "East", "West"],
                        },
                        "spend": {"type": "number", "required": True, "minimum": 0},
                    },
                    "allow_extra_columns": False,
                },
            )
            if not isinstance(schema, dict):
                raise RuntimeError("Schema validation returned an unexpected payload.")
            steps.append({"name": "explicit_schema_validation", "status": "passed"})

            anomalies = _request(
                client,
                "POST",
                f"/api/datasets/{dataset_id}/anomalies",
                json={
                    "detectors": ["iqr", "robust_zscore", "isolation_forest"],
                    "columns": ["amount", "spend"],
                    "contamination": 0.05,
                    "random_state": 42,
                    "n_estimators": 50,
                },
            )
            anomaly_summary = anomalies.get("summary", {})
            if "flagged_row_count" not in anomaly_summary:
                raise RuntimeError("Anomaly review did not return its row summary.")
            steps.append({"name": "anomaly_review", "status": "passed"})

            recommendations = _request(
                client,
                "GET",
                f"/api/datasets/{dataset_id}/cleaning/recommendations",
            )
            if not isinstance(recommendations.get("recommendations"), list):
                raise RuntimeError("Cleaning recommendations were not returned.")
            steps.append({"name": "cleaning_recommendations", "status": "passed"})

            cleaning_request = {
                "drop_exact_duplicates": True,
                "fill_numeric_median": ["amount"],
                "trim_whitespace": ["city"],
            }
            preview = _request(
                client,
                "POST",
                f"/api/datasets/{dataset_id}/cleaning/preview",
                json=cleaning_request,
            )
            if not preview.get("changed") or preview.get("rows_after") != 60:
                raise RuntimeError("The read-only cleaning preview was unexpected.")
            steps.append({"name": "read_only_cleaning_preview", "status": "passed"})

            applied = _request(
                client,
                "POST",
                f"/api/datasets/{dataset_id}/cleaning/apply",
                expected_status=201,
                json=cleaning_request,
            )
            version = applied.get("version", {})
            if version.get("version_number") != 1 or applied.get("source_preserved") is not True:
                raise RuntimeError("Explicit cleaning did not create a preserved immutable version.")
            steps.append({"name": "explicit_cleaning_apply", "status": "passed"})

            versions = _request(
                client, "GET", f"/api/datasets/{dataset_id}/cleaning/versions"
            )
            if len(versions) != 1 or versions[0].get("id") != version.get("id"):
                raise RuntimeError("The immutable version history did not match the applied version.")
            comparison = _request(
                client,
                "GET",
                f"/api/datasets/{dataset_id}/cleaning/versions/"
                f"{version['id']}/quality-comparison",
            )
            if not isinstance(comparison, dict):
                raise RuntimeError("The version comparison returned an unexpected payload.")
            steps.append({"name": "version_history_and_comparison", "status": "passed"})

            readiness = _request(
                client,
                "POST",
                f"/api/datasets/{dataset_id}/ml-readiness",
                json={
                    "target_column": "spend",
                    "task_type": "regression",
                    "feature_columns": ["amount", "city"],
                },
            )
            if not isinstance(readiness.get("warnings"), list) or not isinstance(
                readiness.get("blockers"), list
            ):
                raise RuntimeError("ML-readiness diagnostics were incomplete.")
            steps.append({"name": "ml_readiness", "status": "passed"})

            baseline = _request(
                client,
                "POST",
                f"/api/datasets/{dataset_id}/baseline-model",
                json={
                    "target_column": "spend",
                    "task_type": "regression",
                    "feature_columns": ["amount", "city"],
                    "test_size": 0.25,
                    "random_state": 42,
                },
            )
            metrics = baseline.get("metrics", {})
            if not all(
                key in metrics and math.isfinite(float(metrics[key]))
                for key in ("mae", "rmse", "r2")
            ):
                raise RuntimeError("The regression baseline did not return finite MAE/RMSE/R2.")
            if (
                baseline.get("preprocessing", {}).get("fit_scope")
                != "training_partition_only"
                or baseline.get("preprocessing", {}).get(
                    "test_partition_used_to_fit_preprocessing"
                )
                is not False
            ):
                raise RuntimeError("Baseline preprocessing was not restricted to training rows.")
            steps.append({"name": "leakage_safe_regression_baseline", "status": "passed"})

            stored_uploads = list(upload_dir.glob("*.csv"))
            if len(stored_uploads) != 1 or stored_uploads[0].read_bytes() != payload:
                raise RuntimeError("The original uploaded CSV was modified or replaced.")
            if hashlib.sha256(stored_uploads[0].read_bytes()).hexdigest() != source_sha256:
                raise RuntimeError("The original source SHA-256 changed after cleaning.")
            steps.append({"name": "original_source_integrity", "status": "passed"})

            overview_after = _request(client, "GET", "/api/overview")
            if overview_after.get("dataset_count") != 1:
                raise RuntimeError("The overview did not report exactly one uploaded dataset.")
            steps.append({"name": "api_overview", "status": "passed"})

            return {
                "status": "passed",
                "demo_type": "api_integration_not_browser_e2e",
                "dataset": {
                    "id": dataset_id,
                    "filename": dataset["filename"],
                    "source_rows": profile["shape"]["rows"],
                    "source_columns": profile["shape"]["columns"],
                    "cleaned_rows": version["rows_count"],
                    "source_sha256": source_sha256,
                },
                "quality": {
                    "overall_dqs": dqs["overall"],
                    "issue_count": quality["issue_count"],
                },
                "anomaly_review": {
                    "flagged_row_count": anomaly_summary["flagged_row_count"],
                    "detector_names": list(anomalies.get("detectors", {}).keys()),
                },
                "cleaning": {
                    "preview_rows_before": preview["rows_before"],
                    "preview_rows_after": preview["rows_after"],
                    "version_number": version["version_number"],
                    "source_preserved": applied["source_preserved"],
                    "comparison_completed": True,
                },
                "ml_readiness": {
                    "status": readiness.get("status"),
                    "warning_count": len(readiness["warnings"]),
                    "blocker_count": len(readiness["blockers"]),
                },
                "baseline": {
                    "model": baseline["model"],
                    "metrics": metrics,
                    "train_rows": baseline["split"]["train_rows"],
                    "test_rows": baseline["split"]["test_rows"],
                    "preprocessing_fit_scope": baseline["preprocessing"]["fit_scope"],
                    "test_partition_used_to_fit_preprocessing": False,
                },
                "original_source_preserved": True,
                "steps": steps,
            }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        api_module.initialize_database = previous_initialize
        dataset_ingestion.UPLOAD_DIR = previous_upload_dir
        dataset_cleaning.VERSIONS_DIR = previous_version_dir
        test_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DataSentry's isolated upload-to-baseline API demo."
    )
    parser.parse_args()
    with TemporaryDirectory(prefix="datasentry-demo-") as temporary_dir:
        try:
            report = run_demo(Path(temporary_dir))
        except Exception as exc:
            print(f"DataSentry demo failed: {exc}", file=sys.stderr)
            return 1
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
