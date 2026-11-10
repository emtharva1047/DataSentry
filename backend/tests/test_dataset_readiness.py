"""API tests for deterministic ML-readiness diagnostics."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion


@pytest.fixture
def readiness_client(tmp_path, monkeypatch):
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


def _upload(client, filename, payload):
    response = client.post(
        "/api/datasets/upload",
        files={"file": (filename, payload, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_classification_readiness_reports_missing_target_imbalance_and_copy(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(
        client,
        "classification.csv",
        (
            b"id,mirror,target\n"
            b"1,yes,yes\n2,yes,yes\n3,yes,yes\n4,yes,yes\n"
            b"5,yes,yes\n6,yes,yes\n7,yes,yes\n8,yes,yes\n"
            b"9,yes,yes\n10,no,no\n11,yes,\n"
        ),
    )

    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "classification"},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["readiness_status"] == "review_required"
    assert report["target"]["missing_count"] == 1
    assert report["target"]["completeness_pct"] == 90.91
    assert report["target"]["class_count"] == 2
    assert report["target"]["majority_class_share_pct"] == 90.0
    assert report["target"]["minority_class_count"] == 1
    assert any(item["code"] == "class_imbalance" for item in report["warnings"])
    assert report["leakage_indicators"][0]["feature"] == "mirror"
    assert report["leakage_indicators"][0]["kind"] == "near_exact_target_copy"
    assert report["model_training_performed"] is False


def test_regression_readiness_flags_target_association_and_redundancy(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(
        client,
        "regression.csv",
        (
            b"target,copy,scaled,duplicate\n"
            b"1,1,2,2\n2,2,4,4\n3,3,6,6\n4,4,8,8\n5,5,10,10\n"
            b"6,6,12,12\n7,7,14,14\n8,8,16,16\n9,9,18,18\n10,10,20,20\n"
        ),
    )

    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "regression"},
    )

    assert response.status_code == 200
    report = response.json()
    kinds = {item["kind"] for item in report["leakage_indicators"]}
    assert "near_exact_target_copy" in kinds
    assert "near_perfect_numeric_target_association" in kinds
    assert report["feature_redundancy"]["high_correlation_pairs"]
    assert report["feature_redundancy"]["exact_duplicate_feature_pairs"]


def test_readiness_detects_duplicate_feature_vectors_without_target(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(
        client,
        "duplicates.csv",
        b"target,feature,group\n1,a,x\n0,a,x\n1,b,y\n0,c,z\n0,c,z\n",
    )

    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "classification"},
    )

    assert response.status_code == 200
    duplicate_risk = response.json()["duplicate_split_risk"]
    assert duplicate_risk["duplicate_rows_after_first"] == 2
    assert duplicate_risk["duplicate_groups"] == 2
    assert duplicate_risk["row_numbers"] == [2, 5]


def test_regression_readiness_reports_non_numeric_target_values(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(
        client,
        "bad-target.csv",
        b"target,feature\n1,a\n2,b\nunknown,c\n4,d\n",
    )

    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "regression"},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["target"]["numeric_parseable_count"] == 3
    assert report["target"]["non_numeric_or_non_finite_count"] == 1
    assert any(item["code"] == "non_numeric_regression_target" for item in report["warnings"])


def test_readiness_blocks_single_class_or_all_missing_target(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(
        client,
        "single-class.csv",
        b"target,feature\nyes,a\nyes,b\n,c\n",
    )

    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "classification"},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["readiness_status"] == "blocked"
    assert any(item["code"] == "insufficient_target_classes" for item in report["blockers"])


def test_readiness_rejects_unknown_target_or_features(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(client, "simple.csv", b"target,feature\n1,a\n2,b\n")

    missing_target = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "missing", "task_type": "classification"},
    )
    unknown_feature = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={
            "target_column": "target",
            "task_type": "classification",
            "feature_columns": ["absent"],
        },
    )

    assert missing_target.status_code == 422
    assert unknown_feature.status_code == 422


def test_readiness_rejects_target_as_feature_and_no_features(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(client, "target-only.csv", b"target\nyes\nno\n")

    target_as_feature = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={
            "target_column": "target",
            "task_type": "classification",
            "feature_columns": ["target"],
        },
    )
    no_features = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "classification"},
    )

    assert target_as_feature.status_code == 422
    assert no_features.status_code == 422


def test_readiness_returns_404_for_unknown_dataset(readiness_client):
    response = readiness_client[0].post(
        "/api/datasets/9999/ml-readiness",
        json={"target_column": "target", "task_type": "classification"},
    )
    assert response.status_code == 404


def test_readiness_returns_gone_when_source_is_missing(readiness_client):
    client, upload_dir = readiness_client
    dataset_id = _upload(client, "temporary.csv", b"target,feature\n1,a\n2,b\n")
    next(upload_dir.glob("*.csv")).unlink()

    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={"target_column": "target", "task_type": "regression"},
    )

    assert response.status_code == 410
    assert "unavailable" in response.json()["detail"].lower()


def test_readiness_request_validation_rejects_invalid_thresholds(readiness_client):
    client, _ = readiness_client
    dataset_id = _upload(client, "simple.csv", b"target,feature\n1,a\n2,b\n")
    response = client.post(
        f"/api/datasets/{dataset_id}/ml-readiness",
        json={
            "target_column": "target",
            "task_type": "classification",
            "correlation_threshold": 1.5,
        },
    )
    assert response.status_code == 422
