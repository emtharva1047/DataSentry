"""API tests for leakage-safe baseline classifier and regressor pipelines."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion


@pytest.fixture
def modeling_client(tmp_path, monkeypatch):
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


def _classification_csv():
    rows = ["target,age,city"]
    for index in range(80):
        target = "approved" if index % 2 == 0 else "declined"
        age = "" if index % 13 == 0 else str(20 + index)
        city = "north" if index % 3 else "south"
        rows.append(f"{target},{age},{city}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _regression_csv():
    rows = ["target,area,rooms,segment"]
    for index in range(80):
        target = 12.5 + index * 2.25
        area = "" if index % 11 == 0 else str(500 + index * 15)
        segment = "urban" if index % 3 else "rural"
        rows.append(f"{target},{area},{index % 5 + 1},{segment}")
    rows[7] = "unknown,605,3,urban"
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_classifier_trains_stratified_pipeline_and_preserves_source(modeling_client):
    client, upload_dir = modeling_client
    payload = _classification_csv()
    dataset_id = _upload(client, "classification.csv", payload)
    source_path = next(upload_dir.glob("*.csv"))
    original_bytes = source_path.read_bytes()

    response = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={"target_column": "target", "task_type": "classification", "random_state": 17},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["model"] == "logistic_regression"
    assert report["model_training_performed"] is True
    assert report["split"]["strategy"] == "stratified_random_holdout"
    assert report["split"]["train_rows"] + report["split"]["test_rows"] == 80
    assert report["preprocessing"]["fit_scope"] == "training_partition_only"
    assert report["preprocessing"]["fit_rows"] == report["split"]["train_rows"]
    assert report["preprocessing"]["test_partition_used_to_fit_preprocessing"] is False
    assert "age" in report["features"]["numeric_columns_inferred_from_training"]
    assert "city" in report["features"]["categorical_columns_inferred_from_training"]
    assert set(report["metrics"]) >= {
        "accuracy", "balanced_accuracy", "macro_precision", "macro_recall",
        "macro_f1", "confusion_matrix", "roc_auc",
    }
    assert sum(map(sum, report["metrics"]["confusion_matrix"]["counts"])) == report["split"]["test_rows"]
    assert source_path.read_bytes() == original_bytes
    assert report["source_sha256"]


def test_regressor_drops_invalid_targets_and_returns_regression_metrics(modeling_client):
    client, _ = modeling_client
    dataset_id = _upload(client, "regression.csv", _regression_csv())

    response = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={"target_column": "target", "task_type": "regression", "random_state": 9},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["model"] == "ridge_regression"
    assert report["target"]["excluded_rows"] == 1
    assert report["target"]["eligible_rows"] == 79
    assert report["split"]["strategy"] == "random_holdout"
    assert report["metrics"]["mae"] >= 0
    assert report["metrics"]["rmse"] >= 0
    assert -1 <= report["metrics"]["r2"] <= 1
    assert report["preprocessing"]["test_partition_used_to_fit_preprocessing"] is False


def test_modeling_rejects_single_class_and_too_few_rows(modeling_client):
    client, _ = modeling_client
    dataset_id = _upload(
        client,
        "single-class.csv",
        b"target,feature\nyes,a\nyes,b\nyes,c\nyes,d\nyes,e\nyes,f\nyes,g\nyes,h\nyes,i\nyes,j\n",
    )
    response = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={"target_column": "target", "task_type": "classification"},
    )
    assert response.status_code == 422
    assert "two observed target classes" in response.json()["detail"]


def test_modeling_rejects_unknown_target_and_target_as_feature(modeling_client):
    client, _ = modeling_client
    dataset_id = _upload(client, "classification.csv", _classification_csv())
    missing_target = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={"target_column": "absent", "task_type": "classification"},
    )
    target_as_feature = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={
            "target_column": "target",
            "task_type": "classification",
            "feature_columns": ["target"],
        },
    )
    assert missing_target.status_code == 422
    assert target_as_feature.status_code == 422


def test_modeling_rejects_invalid_feature_and_split_parameters(modeling_client):
    client, _ = modeling_client
    dataset_id = _upload(client, "classification.csv", _classification_csv())
    unknown_feature = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={
            "target_column": "target",
            "task_type": "classification",
            "feature_columns": ["missing"],
        },
    )
    invalid_split = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={
            "target_column": "target",
            "task_type": "classification",
            "test_size": 0.8,
        },
    )
    assert unknown_feature.status_code == 422
    assert invalid_split.status_code == 422


def test_modeling_returns_404_for_unknown_dataset(modeling_client):
    response = modeling_client[0].post(
        "/api/datasets/9999/baseline-model",
        json={"target_column": "target", "task_type": "classification"},
    )
    assert response.status_code == 404


def test_modeling_returns_gone_when_source_is_missing(modeling_client):
    client, upload_dir = modeling_client
    dataset_id = _upload(client, "temporary.csv", _classification_csv())
    next(upload_dir.glob("*.csv")).unlink()
    response = client.post(
        f"/api/datasets/{dataset_id}/baseline-model",
        json={"target_column": "target", "task_type": "classification"},
    )
    assert response.status_code == 410
    assert "unavailable" in response.json()["detail"].lower()
