"""API tests for reproducible, read-only anomaly detection."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion


@pytest.fixture
def anomaly_client(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(dataset_ingestion, "UPLOAD_DIR", upload_dir)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, upload_dir
    app.dependency_overrides.clear()
    test_engine.dispose()


def _upload(client, payload):
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("anomalies.csv", payload, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_all_detectors_flag_extreme_value_and_preserve_original(anomaly_client):
    client, upload_dir = anomaly_client
    payload = (
        b"value,category\n"
        b"1,A\n2,A\n3,B\n4,B\n5,A\n6,A\n"
        b"7,B\n8,B\n9,A\n10,B\n11,A\n1000,B\n"
    )
    dataset_id = _upload(client, payload)
    source_path = next(upload_dir.glob("*.csv"))
    before_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    response = client.post(
        f"/api/datasets/{dataset_id}/anomalies",
        json={
            "detectors": ["iqr", "robust_zscore", "isolation_forest"],
            "contamination": 0.10,
            "random_state": 17,
            "n_estimators": 100,
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["source_sha256"] is not None
    assert report["numeric_columns"][0]["column"] == "value"
    assert report["numeric_columns"][0]["eligible"] is True

    iqr = report["detectors"]["iqr"]
    assert iqr["status"] == "completed"
    assert iqr["columns"][0]["flagged_row_numbers"] == [12]

    robust = report["detectors"]["robust_zscore"]
    assert robust["status"] == "completed"
    assert robust["columns"][0]["flagged_row_numbers"] == [12]

    isolation = report["detectors"]["isolation_forest"]
    assert isolation["status"] == "completed"
    assert 12 in isolation["flagged_row_numbers"]
    assert isolation["parameters"]["random_state"] == 17
    assert isolation["parameters"]["n_estimators"] == 100

    assert 12 in report["summary"]["flagged_row_numbers"]
    assert "data_quality_score" not in report
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before_hash


def test_isolation_forest_is_deterministic_for_same_seed(anomaly_client):
    client, _ = anomaly_client
    dataset_id = _upload(
        client,
        b"value,second\n1,2\n2,3\n3,4\n4,5\n5,6\n6,7\n7,8\n8,9\n9,10\n10,11\n11,12\n1000,13\n",
    )
    request = {
        "detectors": ["isolation_forest"],
        "contamination": 0.10,
        "random_state": 123,
        "n_estimators": 100,
    }

    first = client.post(f"/api/datasets/{dataset_id}/anomalies", json=request)
    second = client.post(f"/api/datasets/{dataset_id}/anomalies", json=request)

    assert first.status_code == second.status_code == 200
    first_result = first.json()["detectors"]["isolation_forest"]
    second_result = second.json()["detectors"]["isolation_forest"]
    assert first_result["flagged_row_numbers"] == second_result["flagged_row_numbers"]
    assert first_result["evidence"] == second_result["evidence"]


def test_selected_non_numeric_column_is_reported_as_ineligible(anomaly_client):
    client, _ = anomaly_client
    dataset_id = _upload(client, b"category\nnorth\nsouth\neast\nwest\n")

    response = client.post(
        f"/api/datasets/{dataset_id}/anomalies",
        json={"columns": ["category"], "detectors": ["iqr", "robust_zscore"]},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["numeric_columns"][0]["eligible"] is False
    assert report["detectors"]["iqr"]["status"] == "skipped"
    assert report["detectors"]["robust_zscore"]["status"] == "skipped"
    assert report["summary"]["flagged_row_count"] == 0


def test_unknown_column_is_rejected(anomaly_client):
    client, _ = anomaly_client
    dataset_id = _upload(client, b"value\n1\n2\n3\n4\n")

    response = client.post(
        f"/api/datasets/{dataset_id}/anomalies",
        json={"columns": ["missing"], "detectors": ["iqr"]},
    )

    assert response.status_code == 422
    assert "Unknown dataset column" in response.json()["detail"]


def test_invalid_detector_parameters_are_rejected(anomaly_client):
    client, _ = anomaly_client
    dataset_id = _upload(client, b"value\n1\n2\n3\n4\n")

    response = client.post(
        f"/api/datasets/{dataset_id}/anomalies",
        json={"contamination": 0.8},
    )

    assert response.status_code == 422


def test_anomaly_endpoint_returns_404_and_410(anomaly_client):
    client, upload_dir = anomaly_client
    missing_dataset = client.post(
        "/api/datasets/9999/anomalies",
        json={"detectors": ["iqr"]},
    )
    assert missing_dataset.status_code == 404

    dataset_id = _upload(client, b"value\n1\n2\n3\n4\n5\n")
    next(upload_dir.glob("*.csv")).unlink()
    unavailable = client.post(
        f"/api/datasets/{dataset_id}/anomalies",
        json={"detectors": ["iqr"]},
    )
    assert unavailable.status_code == 410
