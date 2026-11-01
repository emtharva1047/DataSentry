"""API tests for read-only quality rules and explainable DQS."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion


@pytest.fixture
def quality_client(tmp_path, monkeypatch):
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


def test_quality_rules_and_dqs_report_evidence_and_denominators(quality_client):
    client, _ = quality_client
    dataset_id = _upload(
        client,
        "quality.csv",
        (
            b"name,age,score,city\n"
            b"Alice,20,1,New York\n"
            b"alice,30,2,new york\n"
            b"Bob,40,3,LA \n"
            b"Bob,40,3,LA \n"
            b"Cara,50,bad,\n"
        ),
    )

    response = client.get(f"/api/datasets/{dataset_id}/quality")

    assert response.status_code == 200
    report = response.json()
    issues = {issue["code"] + ":" + str(issue["column"]): issue for issue in report["issues"]}
    assert "missing_values:city" in issues
    assert "duplicate_rows:None" in issues
    assert "type_mismatch:score" in issues
    assert "categorical_inconsistency:name" in issues
    assert "categorical_inconsistency:city" in issues

    assert issues["missing_values:city"]["evidence"]["row_numbers"] == [5]
    assert issues["duplicate_rows:None"]["affected_count"] == 1
    assert issues["duplicate_rows:None"]["evidence"]["row_numbers"] == [4]
    assert issues["type_mismatch:score"]["evidence"]["row_numbers"] == [5]
    assert issues["categorical_inconsistency:city"]["evidence"]["review_required"] is True
    assert issues["categorical_inconsistency:city"]["evidence"]["automatic_normalization"] is False

    score = report["data_quality_score"]
    components = score["components"]
    assert components["completeness"]["numerator"] == 19
    assert components["completeness"]["denominator"] == 20
    assert components["completeness"]["score"] == 95.0
    assert components["validity"]["numerator"] == 9
    assert components["validity"]["denominator"] == 10
    assert components["validity"]["score"] == 90.0
    assert components["uniqueness"]["numerator"] == 4
    assert components["uniqueness"]["denominator"] == 5
    assert components["uniqueness"]["score"] == 80.0
    assert components["consistency"]["numerator"] == 3
    assert components["consistency"]["denominator"] == 9
    assert components["consistency"]["score"] == 33.33
    assert score["overall"] == 78.17
    assert score["active_weight_total"] == 1.0


def test_dqs_renormalizes_when_consistency_is_not_applicable(quality_client):
    client, _ = quality_client
    dataset_id = _upload(client, "numeric.csv", b"age,score\n20,1.5\n30,2.5\n")

    response = client.get(f"/api/datasets/{dataset_id}/quality")

    assert response.status_code == 200
    score = response.json()["data_quality_score"]
    assert score["components"]["consistency"]["applicable"] is False
    assert score["components"]["consistency"]["score"] is None
    assert score["active_weight_total"] == 0.8
    assert score["overall"] == 100.0


def test_quality_returns_404_for_unknown_dataset(quality_client):
    response = quality_client[0].get("/api/datasets/9999/quality")
    assert response.status_code == 404


def test_quality_returns_gone_when_source_file_is_missing(quality_client):
    client, upload_dir = quality_client
    dataset_id = _upload(client, "temporary.csv", b"value\n1\n2\n")
    next(upload_dir.glob("*.csv")).unlink()

    response = client.get(f"/api/datasets/{dataset_id}/quality")

    assert response.status_code == 410
    assert "unavailable" in response.json()["detail"].lower()
